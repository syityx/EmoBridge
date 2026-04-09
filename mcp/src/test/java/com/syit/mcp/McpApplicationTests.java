package com.syit.mcp;

import org.junit.jupiter.api.Test;
import org.springframework.ai.embedding.EmbeddingModel;
import org.springframework.ai.vectorstore.VectorStore;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;

@SpringBootTest
class McpApplicationTests {

	// TODO(engineering-test): Add MCP contract tests for tools/list and tools/call,
	// including argument schema snapshot to prevent accidental breaking changes.
	// TODO(engineering-test): Add integration tests for /mcp endpoint covering auth
	// failure, validation failure, timeout, and tool execution success paths.
	// TODO(engineering-test): Add resilience tests for external dependency failures
	// and verify deterministic error code mapping.

	/**
	 * Mock VectorStore（Chroma）和 EmbeddingModel（OpenAI），
	 * 避免上下文加载测试依赖真实外部服务（Chroma/OpenAI API）。
	 */
	@MockBean
	VectorStore vectorStore;

	@MockBean
	EmbeddingModel embeddingModel;

	@Test
	void contextLoads() {
	}

}
