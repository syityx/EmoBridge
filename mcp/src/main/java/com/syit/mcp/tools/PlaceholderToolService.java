package com.syit.mcp.tools;

import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.stereotype.Service;

@Service
public class PlaceholderToolService {

    @Tool(name = "placeholder_tool", description = "Placeholder MCP tool for integration wiring tests")
    public String placeholderTool(
            @ToolParam(description = "Optional text payload from the agent", required = false) String input) {
        String normalized = input == null ? "" : input.trim();
        if (normalized.isEmpty()) {
            return "placeholder tool not implemented";
        }
        return "placeholder tool not implemented: " + normalized;
    }
}
