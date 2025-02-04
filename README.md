# translate-mod-summary

定时翻译 MCIM 数据库内的 Mod 简介

本项目接入 Deepseek-V3 模型自动将 Mod 的简介翻译为中文

提案可见 <https://github.com/MCLF-CN/docs/issues/15>

对于 Curseforge 暂时只提供 `classId` 为 `6` 的 Mod 的翻译，会继续跟进

已翻译当前所有 Modrinth Project

刷新频率是每天，如果有 Mod 未覆盖请稍后再试

如果 API 有问题请在 [mcim-api issues](https://github.com/mcmod-info-mirror/mcim-api/issues) 提出，翻译质量和遗漏问题在此处 [issues](https://github.com/mcmod-info-mirror/translate-mod-summary/issues) 提出

简介原文来自 Modrinth Project 的 `description` 和 Curseforge Mod 的 `summary` 字段

## 接入说明

详情见[接口文档](https://mod.mcimirror.top/docs#/translate)

### Modrinth

POST `https://mod.mcimirror.top/translate/modrinth`

URL 参数：`project_id`

例如 <https://mod.mcimirror.top/translate/modrinth?project_id=P7dR8mSH>

```json
{
    "project_id": "P7dR8mSH",
    "translated": "轻量级且模块化的API，为使用Fabric工具链的模组提供了常见的钩子功能和互操作性措施。",
    "original": "Lightweight and modular API providing common hooks and intercompatibility measures utilized by mods using the Fabric toolchain.",
    "translated_at": "2025-02-02T08:53:28.638000"
}
```

### Curseforge

POST `https://mod.mcimirror.top/translate/curseforge`

URL 参数：`modId`

例如 <https://mod.mcimirror.top/translate/curseforge?modId=238222>

```json
{
  "modId": 238222,
  "translated": "查看物品和配方",
  "original": "View Items and Recipes",
  "translated_at": "2025-02-02T10:01:52.805000"
}
```

翻译数据见 <https://github.com/mcmod-info-mirror/data>