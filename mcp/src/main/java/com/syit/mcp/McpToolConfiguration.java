package com.syit.mcp;

import com.syit.mcp.tools.PlaceholderToolService;
import org.springframework.ai.tool.method.MethodToolCallbackProvider;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
class McpToolConfiguration {

    @Bean
    MethodToolCallbackProvider methodToolCallbackProvider(PlaceholderToolService placeholderToolService) {
        return MethodToolCallbackProvider.builder().toolObjects(placeholderToolService).build();
    }
}
