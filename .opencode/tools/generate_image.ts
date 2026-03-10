import { tool } from "@opencode-ai/plugin"

export default tool({
    description:
        "Generate manga page image using Nano Banana 2 (gemini-3.1-flash-image-preview). Reads prompt file, collects reference images from character/location assets, and calls Gemini API. Returns JSON with status, message, outputs, updated.",
    args: {
        novel: tool.schema.string().describe("Novel name (must match workspace directory name)"),
        chapter: tool.schema.number().describe("Chapter number"),
        su: tool.schema.number().describe("Story unit number"),
        page: tool.schema.number().describe("Page number"),
    },
    async execute(args, context) {
        const result = await Bun.$`uv run --env-file ${context.worktree}/.env python ${context.worktree}/main.py generate_image --novel ${args.novel} --chapter ${args.chapter} --su ${args.su} --page ${args.page} --workspace ${context.worktree}/workspace`
            .text()
        return result.trim()
    },
})