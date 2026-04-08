from __future__ import annotations

import logging
import uuid

import chromadb
import fitz  # PyMuPDF
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import MarkdownTextSplitter

from core.config import get_settings
from schemas.auth import CurrentUser
from services.auth_service import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _get_chroma_collection() -> chromadb.Collection:
    settings = get_settings()
    client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
    return client.get_or_create_collection(settings.chroma_collection_name)


def _get_embeddings() -> OpenAIEmbeddings:
    settings = get_settings()
    return OpenAIEmbeddings(
        model=settings.embedding_model_name,
        openai_api_key=settings.openai_api_key,
        openai_api_base=settings.openai_base_url,
    )


def _pdf_to_markdown(pdf_bytes: bytes) -> str:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    parts: list[str] = []
    for page_num, page in enumerate(doc, start=1):
        text = page.get_text()
        parts.append(f"## Page {page_num}\n\n{text}")
    doc.close()
    return "\n\n".join(parts)


MAX_PDF_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


@router.post("/upload")
async def upload_pdf(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="请上传 PDF 文件")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="上传的文件为空")

    if len(pdf_bytes) > MAX_PDF_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="文件过大，最大允许 50 MB")

    try:
        markdown_text = _pdf_to_markdown(pdf_bytes)
    except Exception as exc:
        logger.exception("PDF 转换失败")
        raise HTTPException(status_code=422, detail=f"PDF 解析失败: {exc}") from exc

    splitter = MarkdownTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_text(markdown_text)

    if not chunks:
        raise HTTPException(status_code=422, detail="PDF 内容为空，无法切片")

    try:
        embeddings_model = _get_embeddings()
        embeddings_list = embeddings_model.embed_documents(chunks)
    except Exception as exc:
        logger.exception("Embedding 失败")
        raise HTTPException(status_code=502, detail=f"Embedding 服务调用失败: {exc}") from exc

    batch_id = uuid.uuid4().hex[:8]
    filename_stem = file.filename.rsplit(".", 1)[0]
    ids = [f"{filename_stem}_{batch_id}_{i}" for i in range(len(chunks))]
    metadatas = [
        {"source": file.filename, "chunk_index": i, "batch_id": batch_id}
        for i in range(len(chunks))
    ]

    try:
        collection = _get_chroma_collection()
        collection.add(
            ids=ids,
            documents=chunks,
            embeddings=embeddings_list,
            metadatas=metadatas,
        )
    except Exception as exc:
        logger.exception("Chroma 写入失败")
        raise HTTPException(status_code=502, detail=f"Chroma 写入失败: {exc}") from exc

    return {
        "success": True,
        "filename": file.filename,
        "chunks_ingested": len(chunks),
        "batch_id": batch_id,
        "ids": ids,
    }


@router.get("/chroma-data")
def get_chroma_data(current_user: CurrentUser = Depends(get_current_user)) -> dict:
    try:
        collection = _get_chroma_collection()
        result = collection.get(include=["documents", "metadatas"])
    except Exception as exc:
        logger.exception("Chroma 查询失败")
        raise HTTPException(status_code=502, detail=f"Chroma 查询失败: {exc}") from exc

    return {
        "success": True,
        "total": len(result.get("ids") or []),
        "ids": result.get("ids") or [],
        "documents": result.get("documents") or [],
        "metadatas": result.get("metadatas") or [],
    }
