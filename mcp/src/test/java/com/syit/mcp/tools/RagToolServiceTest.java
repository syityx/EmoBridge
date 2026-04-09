package com.syit.mcp.tools;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import org.springframework.ai.document.Document;
import org.springframework.ai.vectorstore.SearchRequest;
import org.springframework.ai.vectorstore.VectorStore;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

/**
 * RagToolService 单元测试：覆盖参数校验与核心返回结构。
 * 使用 Mockito Mock VectorStore，不依赖真实 Chroma 实例。
 */
class RagToolServiceTest {

    @Mock
    private VectorStore vectorStore;

    private RagToolService ragToolService;

    @BeforeEach
    void setUp() {
        MockitoAnnotations.openMocks(this);
        ragToolService = new RagToolService(vectorStore, new ObjectMapper());
    }

    // ── 参数校验测试 ──────────────────────────────────────────────────────────────

    @Test
    void ragSearch_emptyQuery_returnsError() {
        // 空字符串 query 应直接返回错误，不触发 Chroma 检索
        String result = ragToolService.ragSearch("", null);
        assertThat(result).contains("error");
        assertThat(result).contains("query 不能为空");
    }

    @Test
    void ragSearch_nullQuery_returnsError() {
        // null query 同样返回错误
        String result = ragToolService.ragSearch(null, null);
        assertThat(result).contains("error");
    }

    @Test
    void ragSearch_blankQuery_returnsError() {
        // 只有空白字符的 query 应返回错误
        String result = ragToolService.ragSearch("   ", null);
        assertThat(result).contains("error");
    }

    // ── top_k 约束测试 ────────────────────────────────────────────────────────────

    @Test
    void ragSearch_topKExceedsMax_isClamped() throws Exception {
        // top_k = 10 超出上限，应被截断为 3
        when(vectorStore.similaritySearch(any(SearchRequest.class))).thenReturn(List.of());
        String result = ragToolService.ragSearch("test query", 10);
        assertThat(result).contains("\"top_k\":3");
    }

    @Test
    void ragSearch_topKIsNull_usesDefault3() throws Exception {
        // top_k 为 null 时使用默认值 3
        when(vectorStore.similaritySearch(any(SearchRequest.class))).thenReturn(List.of());
        String result = ragToolService.ragSearch("test query", null);
        assertThat(result).contains("\"top_k\":3");
    }

    @Test
    void ragSearch_topKIsNegative_usesDefault3() throws Exception {
        // top_k 为负数时使用默认值 3
        when(vectorStore.similaritySearch(any(SearchRequest.class))).thenReturn(List.of());
        String result = ragToolService.ragSearch("test query", -1);
        assertThat(result).contains("\"top_k\":3");
    }

    // ── 无结果场景测试 ────────────────────────────────────────────────────────────

    @Test
    void ragSearch_noResults_returnsEmptyStructure() throws Exception {
        // Chroma 返回空列表时，应有清晰的空结果结构而非报错
        when(vectorStore.similaritySearch(any(SearchRequest.class))).thenReturn(List.of());
        String result = ragToolService.ragSearch("some query", 3);
        assertThat(result).contains("\"result_count\":0");
        assertThat(result).contains("\"results\":[]");
        assertThat(result).contains("知识库中未找到相关内容");
    }

    // ── 正常检索返回测试 ──────────────────────────────────────────────────────────

    @Test
    void ragSearch_withResults_returnsExpectedStructure() throws Exception {
        // 构造一个带 windows 字段的 Mock Document
        Map<String, Object> meta = Map.of(
                "windows", "前3句...当前句...后2句",
                "source", "test_doc.pdf"
        );
        Document doc = new Document("test sentence text", meta);

        when(vectorStore.similaritySearch(any(SearchRequest.class))).thenReturn(List.of(doc));

        String result = ragToolService.ragSearch("test query", 3);

        // 验证返回结构包含必要字段
        assertThat(result).contains("\"query\":\"test query\"");
        assertThat(result).contains("\"result_count\":1");
        assertThat(result).contains("\"text\":\"test sentence text\"");
        assertThat(result).contains("\"window\":\"前3句...当前句...后2句\"");
        assertThat(result).contains("\"source\":\"test_doc.pdf\"");
        assertThat(result).contains("\"index\":1");
    }

    @Test
    void ragSearch_queryContainsQuotes_doesNotBreakJson() throws Exception {
        // query 含双引号时，返回 JSON 应合法
        when(vectorStore.similaritySearch(any(SearchRequest.class))).thenReturn(List.of());
        String result = ragToolService.ragSearch("query with \"quotes\"", 3);
        // 确保能被 Jackson 解析，不抛异常
        new ObjectMapper().readTree(result);
    }
}
