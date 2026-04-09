package com.syit.mcp;

import com.syit.mcp.tools.PlaceholderToolService;
import com.syit.mcp.tools.RagToolService;
import org.springframework.ai.tool.method.MethodToolCallbackProvider;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
class McpToolConfiguration {

    // TODO(engineering): Move tool registration to a dedicated package and register
    // all tool services via explicit whitelist (do not auto-expose every bean).
    // This avoids accidental exposure when new services are added.

    @Bean
    MethodToolCallbackProvider methodToolCallbackProvider(
            PlaceholderToolService placeholderToolService,
            RagToolService ragToolService) {
        // TODO(engineering): Add profile-based tool sets (dev/staging/prod) so
        // high-risk tools can be disabled in production by configuration.
        return MethodToolCallbackProvider.builder()
                // 注册现有占位工具 + RAG 检索工具
                .toolObjects(placeholderToolService, ragToolService)
                .build();
    }
}
