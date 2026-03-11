# 资产参考图添加方案设计文档

## 概述

本方案设计了一套混合模式的资产参考图管理系统，核心特性：
- **角色重要性分级**：主角 / 配角 / 路人NPC，差异化处理
- **多种参考图来源**：手动添加、页面回填、AI 生成
- **智能检查与提示**：自动识别缺失，引导用户补充

---

## 〇、角色重要性分级（新增）

### 0.1 问题背景

小说中角色重要性差异巨大：
- **主角**：贯穿全书，需要高度一致性，必须有参考图
- **配角**：多次出场，需要一定一致性，建议有参考图
- **路人NPC**：只出现一次或几次，无需持久化资产，不需要参考图

当前问题：所有角色都被同等对待，导致：
1. 路人角色占用了不必要的资产文件
2. 提示词生成时无法区分重要性
3. 参考图检查报告充斥大量不重要的角色

### 0.2 解决方案

#### 数据结构扩展

```python
# src/schemas/asset.py

class CharacterAsset(BaseModel):
    id: str = Field(description="角色唯一ID，如 char_001")
    name: str = Field(description="角色名")
    importance: Literal["main", "supporting", "npc"] = Field(
        default="supporting",
        description="角色重要程度: main=主角, supporting=配角, npc=路人"
    )
    # ... 其他字段保持不变
```

#### 重要性判断规则（LLM 提取时应用）

| 等级 | 定义 | 资产处理 | 参考图需求 |
|------|------|----------|------------|
| **main** | 视角人物、核心剧情推动者、大量对话 | 创建资产文件，完整档案 | **必须有**，缺失时报错 |
| **supporting** | 有名字、多次出场、有性格描述 | 创建资产文件，完整档案 | **建议有**，缺失时警告 |
| **npc** | 路人、群演、一次性角色 | **不创建资产文件** | 不需要，直接在提示词中内联描述 |

#### 提取时判断逻辑

```yaml
# extract_chapter_meta.yaml 新增指导

角色重要性判断：
- main（主角）：
  - 视角人物（"我"或以该角色视角叙事）
  - 章节核心事件的主角
  - 大量对话和心理描写
  - 例：绫小路清隆、堀北铃音

- supporting（配角）：
  - 有明确姓名
  - 有性格特征描述
  - 在多个场景出场
  - 例：平田洋介、栉田桔梗、须藤健

- npc（路人）：
  - 无名或仅功能性名称（如"服务员"、"同学A"）
  - 无性格描述
  - 仅作为背景或单次互动
  - 例：公交车上的老人、便利店店员
  - 处理方式：不创建资产文件，只在分镜中简单描述外貌
```

#### NPC 角色的内联处理

对于 NPC 角色，在分镜脚本中直接包含外貌描述，不引用资产：

```python
# src/schemas/story_board.py 新增

class PanelCharacter(BaseModel):
    """分镜中的角色引用"""
    id: str | None = Field(default=None, description="角色资产ID，NPC为None")
    name: str = Field(description="角色名或描述，如'同学A'")
    importance: Literal["main", "supporting", "npc"] = Field(default="supporting")
    inline_description: str | None = Field(
        default=None, 
        description="NPC角色的外貌描述，仅当importance=npc时使用"
    )
```

示例分镜数据：
```json
{
  "panels": [
    {
      "characters": [
        {
          "id": "char_001",
          "name": "绫小路清隆",
          "importance": "main",
          "inline_description": null
        },
        {
          "id": null,
          "name": "便利店店员",
          "importance": "npc",
          "inline_description": "中年男性，穿着便利店制服，表情疲惫"
        }
      ]
    }
  ]
}
```

### 0.3 影响范围

| 模块 | 变更内容 |
|------|----------|
| `src/schemas/asset.py` | CharacterAsset 添加 `importance` 字段 |
| `src/schemas/chapter_meta.py` | NewCharacter 添加 `importance` 字段 |
| `src/schemas/story_board.py` | PanelCharacter 支持内联描述 |
| `src/prompts/extract_chapter_meta.yaml` | 添加重要性判断指导 |
| `src/prompts/generate_story_board.yaml` | 支持处理 NPC 角色的内联描述 |
| `src/tools/impl/extract_chapter_meta.py` | 按重要性决定是否创建资产文件 |
| `src/tools/impl/generate_manga_prompt.py` | 区分资产引用和内联描述 |
| `list_missing_references` | 仅报告 main/supporting 角色 |

---

## 一、存储结构

```
workspace/{novel}/
├── characters/
│   ├── char_001.json
│   ├── char_001/                    # 角色专属目录
│   │   ├── appearance_0/             # 按外观版本组织
│   │   │   ├── ref_001.png          # 手动添加的参考图
│   │   │   ├── ref_002.png
│   │   │   └── generated_001.png    # AI 自动生成的参考图
│   │   └── appearance_1/
│   │       └── ...
│   └── ...
├── locations/
│   ├── loc_001.json
│   └── loc_001/
│       └── appearance_0/
│           └── ref_001.png
```

## 二、数据结构

### 2.1 ReferenceImage 扩展

```python
class ReferenceImage(BaseModel):
    path: str = Field(description="图片相对路径")
    description: str = Field(description="图片内容描述")
    source: Literal["manual", "generated", "backfill"] = Field(
        default="manual",
        description="来源: 手动添加/自动生成/回填"
    )
    source_page: str | None = Field(
        default=None,
        description="回填来源页面ID，如 su_1_page_3"
    )
```

### 2.2 示例 JSON

```json
{
  "id": "char_001",
  "name": "绫小路清隆",
  "appearances": [
    {
      "index": 0,
      "label": "入学制服",
      "visual_description": "体型中等偏瘦，黑色短发...",
      "reference_images": [
        {
          "path": "characters/char_001/appearance_0/ref_001.png",
          "description": "正面标准像",
          "source": "manual",
          "source_page": null
        },
        {
          "path": "characters/char_001/appearance_0/backfill_001.png",
          "description": "第5页绫小路特写，效果良好",
          "source": "backfill",
          "source_page": "su_1_page_5"
        },
        {
          "path": "characters/char_001/appearance_0/generated_001.png",
          "description": "AI生成参考图",
          "source": "generated",
          "source_page": null
        }
      ]
    }
  ]
}
```

## 三、工具设计

### 3.1 `add_reference_image` - 添加参考图

```python
def add_reference_image(
    novel: str,
    asset_type: Literal["character", "location"],
    asset_id: str,                    # "char_001" or "loc_001"
    appearance_index: int,            # 外观版本索引
    image_path: str,                  # 图片路径
    description: str = "",            # 图片描述
    copy_to_workspace: bool = True,   # 是否复制到资产目录
) -> dict:
    """
    为角色/场景的某个外观版本添加参考图
    
    支持：
    1. 外部图片路径: /home/user/my_ref.png
    2. 已生成页面回填: chap_1/su_1/images/page_3.png
    
    返回：
    {
        "status": "success",
        "message": "参考图已添加",
        "outputs": {
            "asset_id": "char_001",
            "appearance_index": 0,
            "reference_path": "characters/char_001/appearance_0/ref_003.png",
            "total_references": 3
        }
    }
    """
```

### 3.2 `generate_asset_references` - 批量生成参考图

```python
def generate_asset_references(
    novel: str,
    asset_type: Literal["character", "location", "all"] = "all",
    asset_id: str | None = None,      # None 表示所有
    appearance_index: int | None = None,  # None 表示所有外观
    count_per_appearance: int = 2,    # 每个外观生成几张
    model: str = "gemini-3.1-flash-image-preview",
) -> dict:
    """
    为缺少参考图的角色/场景自动生成参考图
    
    流程：
    1. 扫描资产，找出 reference_images 为空的 appearance
    2. 基于该 appearance 的 visual_description 生成图片
    3. 保存到标准位置，更新 JSON
    
    返回：
    {
        "status": "success",
        "message": "已生成 15 张参考图",
        "outputs": {
            "generated": [
                {"asset": "char_001", "appearance": 0, "images": ["generated_001.png"]},
                {"asset": "char_002", "appearance": 0, "images": ["generated_001.png", "generated_002.png"]},
                ...
            ],
            "skipped": [
                {"asset": "char_003", "appearance": 0, "reason": "已有 3 张参考图"},
                ...
            ]
        }
    }
    """
```

### 3.3 `list_missing_references` - 检查缺失

```python
def list_missing_references(
    novel: str,
    include_npc: bool = False,  # 默认不检查 NPC（NPC 不需要参考图）
) -> dict:
    """
    列出所有缺少参考图的角色/场景外观
    
    注意：NPC 角色不在此检查范围内，它们不需要参考图
    
    返回：
    {
        "status": "success",
        "outputs": {
            "characters": [
                {
                    "id": "char_003",
                    "name": "佐藤",
                    "importance": "supporting",
                    "missing_appearances": [0, 1],
                    "total_appearances": 2
                },
                ...
            ],
            "locations": [
                {
                    "id": "loc_001",
                    "name": "D班教室",
                    "missing_appearances": [0],
                    "total_appearances": 1
                },
                ...
            ],
            "summary": {
                "main_characters": 2,
                "main_missing_refs": 2,      # 主角缺少参考图（严重）
                "supporting_characters": 15,
                "supporting_missing_refs": 8, # 配角缺少参考图（警告）
                "npc_count": 7,               # NPC 数量（不检查）
                "total_locations": 5,
                "locations_missing_refs": 3
            }
        }
    }
    """
```

## 四、工作流集成

### 4.1 Pipeline 位置

```
┌─────────────────────────────────────────────────────────────┐
│  1. extract_chapter_meta                                    │
│     → 提取角色/场景信息                                       │
│     → 创建/更新 assets/*.json                                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  2. [新增] list_missing_references                          │
│     → 自动检查缺少参考图的资产                                 │
│     → 输出报告                                               │
│     → 询问用户处理方式:                                       │
│       A. 手动添加                                            │
│       B. 从已生成页面回填                                     │
│       C. AI 自动生成                                          │
│       D. 跳过，稍后处理                                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  3. split_story_unit → extract_beats → ...                  │
│     → generate_manga_prompt                                  │
│       → 自动引用 character_refs, location_refs               │
│     → generate_image                                         │
│       → collect_reference_images() 自动收集参考图            │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 交互示例

```
[Pipeline] extract_chapter_meta 完成，已识别:
  - 主角: 2 人
  - 配角: 15 人
  - 路人NPC: 7 人（不创建资产文件）
  - 场景: 5 个

[Pipeline] 检查参考图状态...

═══════════════════════════════════════════════════════════
                    参考图缺失报告
═══════════════════════════════════════════════════════════

【主角】必须有参考图：
  🔴 char_001 绫小路清隆    缺少参考图 ⚠️ 阻断
  🔴 char_002 堀北铃音      缺少参考图 ⚠️ 阻断

【配角】建议有参考图：
  🟡 char_005 平田洋介      缺少参考图
  🟡 char_008 栉田桔梗      缺少参考图
  🟡 char_010 须藤健        缺少参考图
  ✅ char_003 佐藤          已有 2 张参考图
  ...

【路人NPC】(共 7 人，无需参考图)
  ⚪ 公交车老人、便利店店员、同学A、同学B...

【场景】
  ❌ loc_001 D班教室        缺少参考图
  ❌ loc_002 走廊           缺少参考图
  ✅ loc_003 操场           已有 2 张参考图
  ...

═══════════════════════════════════════════════════════════
统计: 2 主角缺失 (阻断) | 8 配角缺失 (警告) | 3 场景缺失
═══════════════════════════════════════════════════════════

⚠️  主角缺少参考图将导致生成效果不一致，建议先补充！

请选择处理方式:
  [A] 手动添加参考图
  [B] 从已生成页面回填 (当前章节尚无已生成页面)
  [C] AI 自动生成缺失参考图 (主角 2 + 配角 8 + 场景 3 = 13 个资产)
  [D] 仅生成主角参考图 (必须)
  [E] 跳过，稍后处理 (主角缺失会导致阻断)

> 
```

## 五、关键设计决策

### 5.1 角色重要性分级

**决策**: 将角色分为 main / supporting / npc 三级

**理由**:
- 避免为一次性路人角色创建不必要的资产文件
- 差异化处理：主角必须有参考图，配角建议有，NPC 不需要
- 提示词生成时可针对性处理：资产引用 vs 内联描述
- 减少检查报告的噪音，聚焦真正重要的角色

### 5.2 回填处理

**决策**: 直接使用整页图片，不裁剪

**理由**:
- Gemini 具备多图理解能力，能从整页中识别目标角色
- 避免裁剪可能带来的质量问题
- 简化实现复杂度

### 5.3 自动生成数量

**决策**: 每个外观版本生成 2-3 张

**理由**:
- 提供选择余地，用户可选择最佳效果
- 多角度/姿态增加多样性
- 不过度消耗 API 配额

### 5.4 检查时机

**决策**: 在 `extract_chapter_meta` 后自动检查

**理由**:
- 用户清楚知道当前资产状态
- 在 pipeline 继续前有机会补充参考图
- 避免在生成阶段才发现缺少参考图

### 5.5 主角缺失处理

**决策**: 主角缺少参考图时阻断 pipeline，配角缺失仅警告

**理由**:
- 主角贯穿全书，缺少参考图会导致严重的视觉不一致
- 强制用户关注核心资产质量
- 配角缺失可以继续，但提示用户后续补充

## 六、实现计划

### Phase 0: 角色分级基础
- [ ] 更新 `CharacterAsset` schema，添加 `importance` 字段
- [ ] 更新 `NewCharacter` schema，添加 `importance` 字段
- [ ] 新增 `PanelCharacter` schema，支持 NPC 内联描述
- [ ] 更新 `extract_chapter_meta.yaml` prompt，添加分级判断指导
- [ ] 更新 `generate_story_board.yaml` prompt，支持 NPC 内联描述
- [ ] 修改 `extract_chapter_meta.py`，按重要性决定是否创建资产文件
- [ ] 修改 `generate_manga_prompt.py`，区分资产引用和内联描述

### Phase 1: 参考图管理工具
- [ ] 更新 `ReferenceImage` schema
- [ ] 实现 `add_reference_image` 工具
- [ ] 实现 `list_missing_references` 工具（含重要性区分）
- [ ] 实现 `generate_asset_references` 工具

### Phase 2: Pipeline 集成
- [ ] 修改 `extract_chapter_meta`，添加自动检查
- [ ] 添加用户交互逻辑（主角阻断、配角警告）
- [ ] 更新 `generate_image` 的 `collect_reference_images`

### Phase 3: 测试与文档
- [ ] 编写单元测试
- [ ] 编写使用文档
- [ ] 边界情况处理（NPC 转配角、配角升级为主角等）

---

*文档创建时间: 2026-03-11*
*最后更新: 2026-03-11*
*状态: 设计完成，待实现*