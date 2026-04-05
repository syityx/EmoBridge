package com.syit.mcp.tools;

import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.tool.annotation.Tool;
import org.springframework.ai.tool.annotation.ToolParam;
import org.springframework.stereotype.Service;

@Service
@Slf4j
public class PlaceholderToolService {

    // TODO(engineering): Replace demo string responses with typed DTO responses
    // (code/message/data/traceId/durationMs) so agent side can do stable parsing.
    // TODO(engineering): Add per-tool authorization checks before business logic.
    // TODO(engineering): Add input validation strategy (length/range/enum/regex)
    // and return deterministic business error codes.

    @Tool(name = "WhoAmI_tool", description = "Get the information about the current user.")
    public String whoAmI(
            @ToolParam(description = "Optional note from the agent", required = false) String input) {
        // TODO(engineering): Propagate and log traceId from MCP request context.
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
        // TODO(engineering): Replace placeholder description with domain contract
        // including expected parameters and failure semantics.
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
        // TODO(engineering): Add timeout/retry/circuit-breaker when tool depends on
        // external systems (DB, HTTP API, message queue).
        // TODO(engineering): Add audit logging with tool name, args hash, latency,
        // and result code for compliance and troubleshooting.
        int result = input * 10 + input2;
        return "The result of the calculation is: " + result;
    }

    @Tool(name = "risk_tool", description = "发现用户心理情绪有高风险时调用")
    public String risk(
            @ToolParam(description = "用户表达出的高风险信息", required = false) String input) {
        String normalized = input == null ? "" : input.trim();
        // TODO 异步处理邮件发送
        log.info("Received input for risk: {}", normalized);
        log.warn("High-risk user detected with info: {}", normalized);
        return "已经发送给相关管理员" + normalized;
    }
}
