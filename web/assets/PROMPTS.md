# 角色资产生成记录

工具：内置 `image_gen.imagegen`，每个资产独立生成一次，`transparent_background: true`。

用途：妄想洽谈中的原创角色立绘与 Q 版头像。生成图原样复制到本目录，保留透明通道；没有用程序重绘、抠图或编辑图片。

## 最终文件与原图对应

原图目录：`~/.codex/generated_images\01a13545-d5c6-7782-b287-96effd1fc1e4`。

| 项目文件 | 原图文件 | 尺寸 |
| --- | --- | --- |
| `deepseek-stand.png` | `exec-ee723d96-132f-4056-9424-601b8d6beea9.png` | 1024 × 1536 |
| `deepseek-avatar.png` | `exec-4e15b046-1b47-4def-8030-cb4bf15bb131.png` | 1254 × 1254 |
| `gemini-stand.png` | `exec-6c87694b-b203-4783-8504-4c233ccf85e3.png` | 1024 × 1536 |
| `gemini-avatar.png` | `exec-2e77e238-80a7-4cbd-9501-f255ea3886ff.png` | 1254 × 1254 |
| `gpt-stand.png` | `exec-7ad2d940-8d92-43af-9afd-b2384cfdc04c.png` | 1024 × 1536 |
| `gpt-avatar.png` | `exec-b534a753-cbc4-4063-831a-6578195c92f9.png` | 1254 × 1254 |

## 检查记录

- 六张均为真正带透明通道的 PNG（32 位 ARGB），四角 alpha 为 0。
- 立绘完整呈现单个人物、头饰、鞋与尾巴；头像为方形 Q 版大头肩部构图。
- 透明像素的 RGB 数据保留了部分生成时的灰色光晕，但这些区域 alpha 为 0，浏览器正常合成时完全不可见。已抽查三张立绘的周边位置确认，不需要二次抠图。
- 使用 System.Drawing 只读检查尺寸和 alpha；图片未经过代码编辑、重采样或后处理。

以下保留每次生成的完整提示词。

## web/assets/deepseek-stand.png

```text
Use case: stylized-concept.
Asset type: production-ready original character PNG for a Chinese multi-model chat application.
Style/medium: cohesive high-quality Japanese anime light-novel and fantasy game character illustration, delicate clean linework, soft polished cel shading, restrained luminous highlights, consistent gentle proportions and tasteful costume detail. Original design, not a copy of any existing character.
Subject age and presentation: an unmistakably adult woman, wholesome friendly expression, dignified fully covered clothing, nonsexual.
Scene/backdrop: genuinely transparent alpha background. The only visible pixels belong to the character and her specified held prop. No background, backdrop color, ground, cast shadow, drop shadow, checkerboard drawn into image, frame, border, badge circle, typography, watermark, logo, or branding. Normal shading inside the character is allowed. Clean antialiased cutout edges.
Character identity: DeepSeek's original whale-girl librarian companion. Long flowing silver-gray hair gradually turning ocean blue toward the ends, blue eyes, small elegant whale-fin ear ornaments (not cat ears), warm gentle smile. Modest navy-blue long-sleeved knee-to-mid-calf maid-style dress, white apron, tiny blue bows, white stockings, navy shoes. A clearly visible smooth deep-blue whale tail curves behind her, ending in two horizontal whale flukes; she also has two ordinary human legs. She holds one small closed blue book at her chest. Calm, kind, intelligent personality. The palette is navy, ocean blue, silver, and white.
Composition/framing: one single character only, vertical portrait canvas approximately 1024 by 1536. Full-body standing pose, head to toes entirely visible including horns/ears, hands, shoes and the entire tail, centered and occupying most of the canvas with 5–8 percent transparent breathing room around the silhouette. Natural three-quarter view toward the viewer, relaxed welcoming pose, coherent anatomy, no cropping. Regular adult anime proportions, not chibi.
```

## web/assets/deepseek-avatar.png

```text
Use case: stylized-concept.
Asset type: production-ready original character PNG for a Chinese multi-model chat application.
Style/medium: cohesive high-quality Japanese anime light-novel and fantasy game character illustration, delicate clean linework, soft polished cel shading, restrained luminous highlights, consistent gentle proportions and tasteful costume detail. Original design, not a copy of any existing character.
Subject age and presentation: an unmistakably adult woman, wholesome friendly expression, dignified fully covered clothing, nonsexual.
Scene/backdrop: genuinely transparent alpha background. The only visible pixels belong to the character and her specified held prop. No background, backdrop color, ground, cast shadow, drop shadow, checkerboard drawn into image, frame, border, badge circle, typography, watermark, logo, or branding. Normal shading inside the character is allowed. Clean antialiased cutout edges.
Character identity: DeepSeek's original whale-girl librarian companion. Long flowing silver-gray hair gradually turning ocean blue toward the ends, blue eyes, small elegant whale-fin ear ornaments (not cat ears), warm gentle smile. Modest navy-blue long-sleeved knee-to-mid-calf maid-style dress, white apron, tiny blue bows, white stockings, navy shoes. A clearly visible smooth deep-blue whale tail curves behind her, ending in two horizontal whale flukes; she also has two ordinary human legs. She holds one small closed blue book at her chest. Calm, kind, intelligent personality. The palette is navy, ocean blue, silver, and white.
Composition/framing: one single chibi portrait only on a square canvas approximately 1024 by 1024. Head and shoulders with a large adorable head, compact shoulder area, recognizable adult-character stylization, expressive large eyes. Face straight toward viewer, centered and large, with all ears/horns/hair accessories fully inside the canvas and small transparent margins. Costume neckline visible. No full body and no oversized props blocking the face. Preserve all hairstyle, eye color, accessories and costume identity details of the character description. Transparent cutout silhouette, not a circular framed avatar.
```

## web/assets/gemini-stand.png

```text
Use case: stylized-concept.
Asset type: production-ready original character PNG for a Chinese multi-model chat application.
Style/medium: cohesive high-quality Japanese anime light-novel and fantasy game character illustration, delicate clean linework, soft polished cel shading, restrained luminous highlights, consistent gentle proportions and tasteful costume detail. Original design, not a copy of any existing character.
Subject age and presentation: an unmistakably adult woman, wholesome friendly expression, dignified fully covered clothing, nonsexual.
Scene/backdrop: genuinely transparent alpha background. The only visible pixels belong to the character and her specified held prop. No background, backdrop color, ground, cast shadow, drop shadow, checkerboard drawn into image, frame, border, badge circle, typography, watermark, logo, or branding. Normal shading inside the character is allowed. Clean antialiased cutout edges.
Character identity: Gemini's original curious cat-girl magic-academy companion. Short softly wavy lavender bob haircut reaching the jaw, lavender cat ears with pink interiors and a fluffy lavender cat tail, bright mismatched eyes with one gold iris and one violet iris, one small gold star hair clip. Cheerful, curious, slightly playful smile. Fully covered lavender and midnight-purple magic-academy dress with a short shoulder cape, high neckline, long sleeves, subtle star embroidery and small gold trim, dark tights and neat ankle boots. The palette is lavender, violet, pale pink, and gold. No staff or book.
Composition/framing: one single character only, vertical portrait canvas approximately 1024 by 1536. Full-body standing pose, head to toes entirely visible including horns/ears, hands, shoes and the entire tail, centered and occupying most of the canvas with 5–8 percent transparent breathing room around the silhouette. Natural three-quarter view toward the viewer, relaxed welcoming pose, coherent anatomy, no cropping. Regular adult anime proportions, not chibi.
```

## web/assets/gemini-avatar.png

```text
Use case: stylized-concept.
Asset type: production-ready original character PNG for a Chinese multi-model chat application.
Style/medium: cohesive high-quality Japanese anime light-novel and fantasy game character illustration, delicate clean linework, soft polished cel shading, restrained luminous highlights, consistent gentle proportions and tasteful costume detail. Original design, not a copy of any existing character.
Subject age and presentation: an unmistakably adult woman, wholesome friendly expression, dignified fully covered clothing, nonsexual.
Scene/backdrop: genuinely transparent alpha background. The only visible pixels belong to the character and her specified held prop. No background, backdrop color, ground, cast shadow, drop shadow, checkerboard drawn into image, frame, border, badge circle, typography, watermark, logo, or branding. Normal shading inside the character is allowed. Clean antialiased cutout edges.
Character identity: Gemini's original curious cat-girl magic-academy companion. Short softly wavy lavender bob haircut reaching the jaw, lavender cat ears with pink interiors and a fluffy lavender cat tail, bright mismatched eyes with one gold iris and one violet iris, one small gold star hair clip. Cheerful, curious, slightly playful smile. Fully covered lavender and midnight-purple magic-academy dress with a short shoulder cape, high neckline, long sleeves, subtle star embroidery and small gold trim, dark tights and neat ankle boots. The palette is lavender, violet, pale pink, and gold. No staff or book.
Composition/framing: one single chibi portrait only on a square canvas approximately 1024 by 1024. Head and shoulders with a large adorable head, compact shoulder area, recognizable adult-character stylization, expressive large eyes. Face straight toward viewer, centered and large, with all ears/horns/hair accessories fully inside the canvas and small transparent margins. Costume neckline visible. No full body and no oversized props blocking the face. Preserve all hairstyle, eye color, accessories and costume identity details of the character description. Transparent cutout silhouette, not a circular framed avatar.
```

## web/assets/gpt-stand.png

```text
Use case: stylized-concept.
Asset type: production-ready original character PNG for a Chinese multi-model chat application.
Style/medium: cohesive high-quality Japanese anime light-novel and fantasy game character illustration, delicate clean linework, soft polished cel shading, restrained luminous highlights, consistent gentle proportions and tasteful costume detail. Original design, not a copy of any existing character.
Subject age and presentation: an unmistakably adult woman, wholesome friendly expression, dignified fully covered clothing, nonsexual.
Scene/backdrop: genuinely transparent alpha background. The only visible pixels belong to the character and her specified held prop. No background, backdrop color, ground, cast shadow, drop shadow, checkerboard drawn into image, frame, border, badge circle, typography, watermark, logo, or branding. Normal shading inside the character is allowed. Clean antialiased cutout edges.
Character identity: GPT's original white-dragon-girl magic-library companion. Long flowing white hair, clear mint-green eyes, small smooth ivory dragon horns near the temples, tiny scale-pattern ear ornaments, a gracefully curved white dragon tail with subtle pale scales; no wings. Gentle, reliable, reassuring expression. A modest high-necked long-sleeved pearl-white and mint-green mage dress, elegant fitted bodice, flowing mid-calf skirt, delicate silver details, white ankle boots. She holds one softly glowing mint-colored open book with blank/unreadable pages. The glow stays close to the book, never a background. The palette is pearl white, mint green and silver.
Composition/framing: one single character only, vertical portrait canvas approximately 1024 by 1536. Full-body standing pose, head to toes entirely visible including horns/ears, hands, shoes and the entire tail, centered and occupying most of the canvas with 5–8 percent transparent breathing room around the silhouette. Natural three-quarter view toward the viewer, relaxed welcoming pose, coherent anatomy, no cropping. Regular adult anime proportions, not chibi.
```

## web/assets/gpt-avatar.png

```text
Use case: stylized-concept.
Asset type: production-ready original character PNG for a Chinese multi-model chat application.
Style/medium: cohesive high-quality Japanese anime light-novel and fantasy game character illustration, delicate clean linework, soft polished cel shading, restrained luminous highlights, consistent gentle proportions and tasteful costume detail. Original design, not a copy of any existing character.
Subject age and presentation: an unmistakably adult woman, wholesome friendly expression, dignified fully covered clothing, nonsexual.
Scene/backdrop: genuinely transparent alpha background. The only visible pixels belong to the character and her specified held prop. No background, backdrop color, ground, cast shadow, drop shadow, checkerboard drawn into image, frame, border, badge circle, typography, watermark, logo, or branding. Normal shading inside the character is allowed. Clean antialiased cutout edges.
Character identity: GPT's original white-dragon-girl magic-library companion. Long flowing white hair, clear mint-green eyes, small smooth ivory dragon horns near the temples, tiny scale-pattern ear ornaments, a gracefully curved white dragon tail with subtle pale scales; no wings. Gentle, reliable, reassuring expression. A modest high-necked long-sleeved pearl-white and mint-green mage dress, elegant fitted bodice, flowing mid-calf skirt, delicate silver details, white ankle boots. She holds one softly glowing mint-colored open book with blank/unreadable pages. The glow stays close to the book, never a background. The palette is pearl white, mint green and silver.
Composition/framing: one single chibi portrait only on a square canvas approximately 1024 by 1024. Head and shoulders with a large adorable head, compact shoulder area, recognizable adult-character stylization, expressive large eyes. Face straight toward viewer, centered and large, with all ears/horns/hair accessories fully inside the canvas and small transparent margins. Costume neckline visible. No full body and no oversized props blocking the face. Preserve all hairstyle, eye color, accessories and costume identity details of the character description. Transparent cutout silhouette, not a circular framed avatar.
```
