package com.syit.mcp.tools;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.document.Document;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.ai.vectorstore.SearchRequest;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * RAG 检索工具服务：对接 Chroma 向量数据库，向 MCP Agent 暴露 rag_search 工具。
 *
 * <p>知识入库方式：每条句子以句子-窗口法存储，metadata.windows 字段保存该句的
 * 前 3 句 + 后 2 句上下文，供 LLM 理解更完整的语义背景。
 *
 * <p>当前版本：仅做向量召回（top-k ≤ 3），暂不支持重排（Reranker）。
 */
@Service
@Slf4j
public class RagToolService {

    /** 向量数据库（Chroma），由 Spring AI 自动装配 */
    private final VectorStore vectorStore;

    /** JSON 序列化工具，由 Spring Boot 自动装配 */
    private final ObjectMapper objectMapper;

    /** 单次检索最大返回条数（暂不支持重排，固定上限为 3） */
    private static final int MAX_TOP_K = 3;

    public RagToolService(VectorStore vectorStore, ObjectMapper objectMapper) {
        this.vectorStore = vectorStore;
        this.objectMapper = objectMapper;
    }

    /**
     * 从知识库（Chroma）向量检索与查询词最相关的文本片段（top-3）。
     *
     * <p>每条结果包含：
     * <ul>
     *   <li>text     – 原句文本（精确引用点）</li>
     *   <li>window   – 上下文窗口（前3后2句，更完整的语义背景）</li>
     *   <li>score    – 相关性分数（越大越相关）</li>
     *   <li>source   – 来源文件</li>
     *   <li>id       – 文档 ID</li>
     * </ul>
     *
     * @param query 检索查询词，从用户问题提炼关键词，不要整段照抄
     * @param topK  返回结果数量，默认 3，超过 3 自动截断
     * @return JSON 字符串：{query, top_k, result_count, results[]}；出错时含 error 字段
     */
    @Tool(
        name = "rag_search",
        description = "从知识库中向量检索与 query 最相关的文本片段（top-3），每条结果包含原句(text)、"
                    + "上下文窗口(window)、相关性分数(score)及来源元数据。"
                    + "凡涉及项目文档、业务规则、接口参数、配置流程、实现细节的问题，必须先调用此工具再回答。"
    )
    public String ragSearch(
            @ToolParam(description = "检索查询词，从用户问题中提炼关键词，不要整段照抄用户问题", required = true)
            String query,
            @ToolParam(description = "返回结果数量，默认 3，超过 3 自动截断为 3", required = false)
            Integer topK) {

        // ── 1. 参数校验 ──────────────────────────────────────────────────────────
        if (query == null || query.isBlank()) {
            log.warn("[rag_search] 收到空 query，拒绝检索");
            return buildErrorJson("query 不能为空");
        }

        // top_k 约束：最小 1，最大 MAX_TOP_K（3）；null 或非正数时取默认值 3
        int k = (topK == null || topK < 1) ? MAX_TOP_K : Math.min(topK, MAX_TOP_K);

        log.info("[rag_search] query=\"{}\", k={}", query, k);

        // ── 2. 向量检索 ──────────────────────────────────────────────────────────
        List<Document> docs;
        try {
            SearchRequest request = SearchRequest.builder()
                    .query(query.trim())
                    .topK(k)
                    .build();
            docs = vectorStore.similaritySearch(request);
        } catch (Exception e) {
            log.error("[rag_search] Chroma 检索异常: {}", e.getMessage(), e);
            return buildErrorJson("知识库检索失败: " + e.getMessage());
        }

        // ── 3. 无结果处理 ────────────────────────────────────────────────────────
        if (docs == null || docs.isEmpty()) {
            log.info("[rag_search] 未检索到结果, query=\"{}\"", query);
            return buildEmptyJson(query.trim(), k);
        }

        // ── 4. 构造 LLM 友好的返回结构 ──────────────────────────────────────────
        List<Map<String, Object>> results = new ArrayList<>();
        for (int i = 0; i < docs.size(); i++) {
            Document doc = docs.get(i);
            // 取 metadata，防止 null
            Map<String, Object> meta = doc.getMetadata() != null ? doc.getMetadata() : Map.of();

            // 从 metadata 取 windows 字段（知识入库时存储的前3后2上下文）
            String window = String.valueOf(meta.getOrDefault("windows", ""));
            String source = String.valueOf(meta.getOrDefault("source", ""));

            // 获取相关性分数（Spring AI 将 Chroma 距离转换为分数后存入 Document）
            Double score = doc.getScore();

            Map<String, Object> item = new LinkedHashMap<>();
            // index 从 1 开始，便于 LLM 以 [KB1][KB2][KB3] 格式引用
            item.put("index", i + 1);
            item.put("id", doc.getId());
            item.put("score", score);
            item.put("text", doc.getText());   // 原句文本
            item.put("window", window);         // 上下文窗口（前3后2句）
            item.put("source", source);
            item.put("metadata", meta);
            results.add(item);
        }

        // ── 5. 序列化并返回 ──────────────────────────────────────────────────────
        try {
            Map<String, Object> response = new LinkedHashMap<>();
            response.put("query", query.trim());
            response.put("top_k", k);
            response.put("result_count", results.size());
            response.put("results", results);
            return objectMapper.writeValueAsString(response);
        } catch (Exception e) {
            log.error("[rag_search] JSON 序列化失败: {}", e.getMessage(), e);
            return buildErrorJson("结果序列化失败: " + e.getMessage());
        }
    }

    // ── 私有辅助方法 ──────────────────────────────────────────────────────────────

    /**
     * 构造错误响应 JSON（格式简单，避免序列化器依赖）。
     *
     * @param message 错误描述
     * @return JSON 字符串
     */
    private String buildErrorJson(String message) {
        // 转义双引号，防止 JSON 格式破坏
        String escaped = message.replace("\\", "\\\\").replace("\"", "\\\"");
        return "{\"error\":\"" + escaped + "\",\"results\":[]}";
    }

    /**
     * 构造无结果响应 JSON。
     *
     * @param query 原始查询词
     * @param k     请求的 top_k
     * @return JSON 字符串
     */
    private String buildEmptyJson(String query, int k) {
        String escaped = query.replace("\\", "\\\\").replace("\"", "\\\"");
        return "{\"query\":\"" + escaped + "\","
             + "\"top_k\":" + k + ","
             + "\"result_count\":0,"
             + "\"results\":[],"
             + "\"message\":\"知识库中未找到相关内容，请尝试改写查询词后重试\"}";
    }
}
