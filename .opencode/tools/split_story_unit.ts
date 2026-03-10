import { tool } from "@opencode-ai/plugin"

export default tool({
    description:
        "Split a chapter into story units based on narrative boundaries. Returns JSON with status, message, outputs, updated.",
    args: {
        novel: tool.schema.string().describe("Novel name (must match workspace directory name)"),
        chapter: tool.schema.number().describe("Chapter number"),
        model: tool.schema.string().optional().describe("LLM model name (e.g., deepseek-chat, gpt-4o). If not specified, uses default model."),
    },
    async execute(args, context) {
        const cmd = ["uv", "run", "--env-file", `${context.worktree}/.env`, "python", `${context.worktree}/main.py`, "split_story_unit", "--novel", args.novel, "--chapter", String(args.chapter), "--workspace", `${context.worktree}/workspace`]
        if (args.model) {
            cmd.push("--model", args.model)
        }
        const result = await Bun.$`${cmd}`.text()
        return result.trim()
    },
})