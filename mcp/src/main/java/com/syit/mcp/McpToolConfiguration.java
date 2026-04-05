package com.syit.mcp;

import com.syit.mcp.tools.PlaceholderToolService;
import org.springframework.ai.tool.method.MethodToolCallbackProvider;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
class McpToolConfiguration {

    // TODO(engineering): Move tool registration to a dedicated package and register
    // all tool services via explicit whitelist (do not auto-expose every bean).
    // This avoids accidental exposure when new services are added.

    @Bean
    MethodToolCallbackProvider methodToolCallbackProvider(PlaceholderToolService placeholderToolService) {
        // TODO(engineering): Add profile-based tool sets (dev/staging/prod) so
        // high-risk tools can be disabled in production by configuration.
        return MethodToolCallbackProvider.builder().toolObjects(placeholderToolService).build();
    }
}
