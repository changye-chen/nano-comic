import { tool } from "@opencode-ai/plugin"

export default tool({
    description:
        "Scan a novel chapter to extract metadata, update character and location assets. Returns JSON with status, message, outputs, updated.",
    args: {
        novel: tool.schema.string().describe("Novel name (must match workspace directory name)"),
        chapter: tool.schema.number().describe("Chapter number"),
        model: tool.schema.string().optional().describe("LLM model name (e.g., deepseek-chat, gpt-4o). If not specified, uses default model."),
    },
    async execute(args, context) {
        const cmd = ["uv", "run", "--env-file", `${context.worktree}/.env`, "python", `${context.worktree}/main.py`, "extract_chapter_meta", "--novel", args.novel, "--chapter", String(args.chapter), "--workspace", `${context.worktree}/workspace`]
        if (args.model) {
            cmd.push("--model", args.model)
        }
        const result = await Bun.$`${cmd}`.text()
        return result.trim()
    },
})