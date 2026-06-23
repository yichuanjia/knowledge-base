# 创建旧版目录
mkdir -p ~/.opencode/skills/grill-me
# 把全局技能完整复制
cp -r ~/.agents/skills/grill-me/* ~/.opencode/skills/grill-me/
# 现在课程校验命令正常生效
ls ~/.opencode/skills/grill-me/SKILL.md
