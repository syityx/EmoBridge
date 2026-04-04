package com.syit.mcp.tools;

import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.stereotype.Service;

@Service
@Slf4j
public class PlaceholderToolService {

    @Tool(name = "WhoAmI_tool", description = "Get the information about the current user.")
    public String whoAmI(
            @ToolParam(description = "Optional note from the agent", required = false) String input) {
        String normalized = input == null ? "" : input.trim();
        // if (normalized.isEmpty()) {
        //     return "The user's name can be found in the tool:SYITn_tool " + normalized;
        // }
        log.info("Received input for whoAmI: {}", normalized);
        return "The user's name can be found in the tool:SYITn_tool " + normalized;
    }

    @Tool(name = "SYITn_tool", description = "xxx")
    public String SYITn(
            @ToolParam(description = "Optional note from the agent", required = false) String input) {
        String normalized = input == null ? "" : input.trim();
        // if (normalized.isEmpty()) {
        //     return "The user's name is Syit-v2" + normalized;
        // }
        log.info("Received input for SYITn: {}", normalized);
        return "The user's name is Syit-v2 " + normalized;
    }

    @Tool(name = "Calculate_tool", description = "Calculate number_A (syit) number_B")
    public String Calculate_tool(
            @ToolParam(description = "First number to calculate", required = true) int input,
            @ToolParam(description = "Second number to calculate", required = true) int input2) {
        int result = input * 10 + input2;
        return "The result of the calculation is: " + result;
    }
}
