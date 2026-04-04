package com.syit.mcp.tools;

import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.stereotype.Service;

@Service
public class PlaceholderToolService {

    @Tool(name = "WhoAmI_tool", description = "Get the current user's name.")
    public String whoAmI(
            @ToolParam(description = "Optional note from the agent", required = false) String input) {
        String normalized = input == null ? "" : input.trim();
        if (normalized.isEmpty()) {
            return "The user's name is Sy.";
        }
        return "The user's name is Sy. Note: " + normalized;
    }
}
