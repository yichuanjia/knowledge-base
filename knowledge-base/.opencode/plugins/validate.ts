import type { Plugin } from "@opencode-ai/plugin"

const TARGET_DIR = "knowledge/articles"

function isTargetFile(toolName: string, filePath: string): boolean {
  return (
    (toolName === "write" || toolName === "edit") &&
    filePath.includes(TARGET_DIR) &&
    filePath.endsWith(".json")
  )
}

export const ValidatePlugin: Plugin = async ({ $, client }) => {
  return {
    "tool.execute.after": async (input) => {
      const toolName: string = input.tool
      const filePath: string =
        input.args?.file_path ?? input.args?.filePath ?? ""

      if (!isTargetFile(toolName, filePath)) {
        return
      }

      try {
        const validate =
          await $`python3 hooks/validate_json.py ${filePath}`.nothrow()

        if (validate.exitCode !== 0) {
          const errors = validate.stderr.toString().trim()
          await client.app.log({
            body: {
              service: "validate-plugin",
              level: "warn",
              message: `校验失败: ${filePath}\n${errors}`,
            },
          })
          throw new Error(
            `[校验失败] ${filePath} 存在以下问题需要修复:\n${errors}`
          )
        }

        const quality =
          await $`python3 hooks/check_quality.py ${filePath}`.nothrow()

        const stdout = quality.stdout.toString().trim()
        const gradeMatch = stdout.match(/等级:\s*([ABC])/)
        const scoreMatch = stdout.match(/总分:\s*([\d.]+)\/100/)

        if (gradeMatch && scoreMatch) {
          const grade = gradeMatch[1]
          const score = scoreMatch[1]

          await client.app.log({
            body: {
              service: "validate-plugin",
              level: "info",
              message: `${filePath}: ${score}/100 (${grade}级)`,
            },
          })

          if (grade === "C") {
            throw new Error(
              `[质量不合格] ${filePath} 评分 ${score}/100 (C级)，需要提升至 B 级以上。\n` +
              `主要问题维度请查看质量报告并修复。`
            )
          }
        }
      } catch (err) {
        if (err instanceof Error) {
          throw err
        }
        await client.app.log({
          body: {
            service: "validate-plugin",
            level: "error",
            message: `校验异常: ${filePath} — ${String(err)}`,
          },
        })
      }
    },
  }
}
