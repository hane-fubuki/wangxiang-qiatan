# 参考图 Q 版资产记录

三张立绘直接复制用户原始 JPG，界面只用 CSS 等比例显示，不重绘、不抠图、不改色：

| 角色 | 立绘文件 | SHA-256（与用户原图相同） |
| --- | --- | --- |
| DeepSeek | `deepseek-original.jpg` | `3356587068538D39F0EBFCBEB5A38C95B40B4F63EC6F62F573FD94452B616851` |
| Gemini | `gemini-original.jpg` | `72F64F0B7DFB76C5B131CFFC379FFD139E21F3688AA91D5208B45344806751FC` |
| GPT | `gpt-original.jpg` | `FE7017E670D703FE4169CB1EEEE654FC6158FDF8D538CC9DE88E8A1A1790F691` |

生成日期：2026-10-13。

工具：内置 `image_gen.imagegen`。每张使用对应的用户参考图作为 `referenced_image_paths`，`transparent_background: true`，共 3 次调用。生成前已逐张查看本地原图，生成后逐张检查风格、身份特征与透明通道。未使用 CLI；未用代码绘图、抠图或修改图片。

参考原图目录：`~/.codex/codex-remote-attachments\01a13541-f1a7-7990-b0d6-25d98e4282e7\8D66CC88-6AD5-4EA2-B1F4-CD296B8C4B5A`。

生成原图目录：`~/.codex/generated_images\01a13545-d5c6-7782-b287-96effd1fc1e4`。

## 文件映射

| 角色 | 用户参考图 | 项目 Q 版文件 | 内置工具生成原图 |
| --- | --- | --- | --- |
| deepseek | `1-照片-1.jpg` | `deepseek-avatar-reference.png` | `exec-ec01f26f-d319-4cbd-a558-73dc3e407462.png` |
| gemini | `2-照片-2.jpg` | `gemini-avatar-reference.png` | `exec-2e8165c7-b04d-4386-811a-abdee7f40df7.png` |
| gpt | `3-照片-3.jpg` | `gpt-avatar-reference.png` | `exec-6b108f1a-e048-4326-a9f8-cf80dab61be4.png` |

所有最终文件均为 1254 × 1254 的 32 位 RGBA/ARGB PNG。检查使用 System.Drawing 只读读取尺寸与 alpha；左右上角 alpha 均为 0，透明区域抽样比例分别为 DeepSeek 35.84%、Gemini 27.76%、GPT 33.16%。最终文件为内置生成原图的原样复制，旧版头像保留。

## 身份与画风检查

- DeepSeek：深蓝渐浅蓝长发、蓝眼、横向鲸鳍耳、白色女仆发箍、蓝白女仆裙与深色颈蝴蝶结。
- Gemini：长蓝紫渐粉发、双侧盘髻、猫耳猫尾、画面左粉眼与右金眼、彩色四芒星发饰、深紫星星服装。
- GPT：白色长发、淡紫眼、分节白龙角、尖耳、白色翅膀与龙尾、结状发饰与银白衣。
- 统一为简化大头小肩身的日系 Q 版，清楚轮廓、较少赛璐璐阴影；避免上一版细密发丝、油画感、浓妆与大面积高光。

## 完整提示词

### deepseek-avatar-reference.png

参考图：`~/.codex/codex-remote-attachments/01a13541-f1a7-7990-b0d6-25d98e4282e7/8D66CC88-6AD5-4EA2-B1F4-CD296B8C4B5A/1-照片-1.jpg`

```text
Use case: style-transfer.
Input image: the attached/local reference is the authoritative character identity reference. Transform this exact adult anime character into a clean, simple chibi avatar; do not invent or substitute her identity.
Asset: one square 1:1 PNG portrait with a real transparent alpha background for a small chat avatar. One character only. Large cute head and small shoulders/upper torso, head about 70 percent of the character height in the frame. Front-facing or very slight three-quarter view. All ears, horns, ahoge and head accessories must fit fully inside the square with a modest transparent margin. Face large, clear, easy to recognize at 48 pixels.
Style: clean flat Japanese chibi anime drawing, confident medium-weight smooth dark colored outlines, broad simplified hair shapes, flat base colors with only 2 to 3 discrete cel-shading tones, minimal tiny details. Natural cute expression. No painterly brushwork, no oily or glossy skin, no detailed individual hair strands, no heavy blush or cosmetics, no rendered gradients across the face, no photorealistic volume, no glow, no lens effects, no elaborate gilding, no ornamental frame, no background, no shadow outside the character. Transparent pixels outside the crisp silhouette. Do not draw a checkerboard. No new props or books. No text, caption, watermark or logo added.
Character-specific invariants:
Preserve the reference whale girl's long deep indigo-blue hair with pale ocean-blue ends (NOT silver, gray, white or blonde), bright blue eyes, long sideways whale-fin-shaped ears, white frilled maid headdress, small blue side bows, dark navy bow at the neck with pale oval center, navy and white frilled maid outfit. Keep the single looped ahoge and the recognizable broad hairstyle. Friendly open small smile. A small simple blue whale-tail fluke may peek behind the shoulder only if it fits cleanly; prioritize her face and fin ears. Match the identity and design of reference image exactly, simplified into chibi.
```

### gemini-avatar-reference.png

参考图：`~/.codex/codex-remote-attachments/01a13541-f1a7-7990-b0d6-25d98e4282e7/8D66CC88-6AD5-4EA2-B1F4-CD296B8C4B5A/2-照片-2.jpg`

```text
Use case: style-transfer.
Input image: the attached/local reference is the authoritative character identity reference. Transform this exact adult anime character into a clean, simple chibi avatar; do not invent or substitute her identity.
Asset: one square 1:1 PNG portrait with a real transparent alpha background for a small chat avatar. One character only. Large cute head and small shoulders/upper torso, head about 70 percent of the character height in the frame. Front-facing or very slight three-quarter view. All ears, horns, ahoge and head accessories must fit fully inside the square with a modest transparent margin. Face large, clear, easy to recognize at 48 pixels.
Style: clean flat Japanese chibi anime drawing, confident medium-weight smooth dark colored outlines, broad simplified hair shapes, flat base colors with only 2 to 3 discrete cel-shading tones, minimal tiny details. Natural cute expression. No painterly brushwork, no oily or glossy skin, no detailed individual hair strands, no heavy blush or cosmetics, no rendered gradients across the face, no photorealistic volume, no glow, no lens effects, no elaborate gilding, no ornamental frame, no background, no shadow outside the character. Transparent pixels outside the crisp silhouette. Do not draw a checkerboard. No new props or books. No text, caption, watermark or logo added.
Character-specific invariants:
Preserve the reference cat girl's LONG flowing blue-violet hair with purple, pink and light-blue tips, the small round coiled hair buns on BOTH sides, the single ahoge, blue-violet cat ears with pink interiors. Keep heterochromia EXACTLY as in the reference: the eye on the VIEWER'S LEFT is pink/magenta; the eye on the VIEWER'S RIGHT is golden yellow. Keep the large multicolored four-point star hair clip beside the viewer-right cat ear, with its small dangling star. Keep the dark navy-violet star-themed high collar, white chest inset, cut-out shoulder silhouette and wide detached sleeves from the reference in a modest head-and-upper-torso crop. Long locks remain visibly long below the shoulders: absolutely not a short bob. Cheerful curious expression with a small playful smile, no exaggerated blush. Optional small fluffy purple-blue tail edge behind a shoulder. The outfit and face must match reference identity, simplified into chibi.
```

### gpt-avatar-reference.png

参考图：`~/.codex/codex-remote-attachments/01a13541-f1a7-7990-b0d6-25d98e4282e7/8D66CC88-6AD5-4EA2-B1F4-CD296B8C4B5A/3-照片-3.jpg`

```text
Use case: style-transfer.
Input image: the attached/local reference is the authoritative character identity reference. Transform this exact adult anime character into a clean, simple chibi avatar; do not invent or substitute her identity.
Asset: one square 1:1 PNG portrait with a real transparent alpha background for a small chat avatar. One character only. Large cute head and small shoulders/upper torso, head about 70 percent of the character height in the frame. Front-facing or very slight three-quarter view. All ears, horns, ahoge and head accessories must fit fully inside the square with a modest transparent margin. Face large, clear, easy to recognize at 48 pixels.
Style: clean flat Japanese chibi anime drawing, confident medium-weight smooth dark colored outlines, broad simplified hair shapes, flat base colors with only 2 to 3 discrete cel-shading tones, minimal tiny details. Natural cute expression. No painterly brushwork, no oily or glossy skin, no detailed individual hair strands, no heavy blush or cosmetics, no rendered gradients across the face, no photorealistic volume, no glow, no lens effects, no elaborate gilding, no ornamental frame, no background, no shadow outside the character. Transparent pixels outside the crisp silhouette. Do not draw a checkerboard. No new props or books. No text, caption, watermark or logo added.
Character-specific invariants:
Preserve the reference white-dragon girl's long pure white hair, pale lavender/lilac eyes (NOT green or teal), two tall upward-curving segmented white dragon horns, small pointed elf-like ears, the looped top ahoge, and the pale interwoven knot-shaped flower hair ornament with a tassel beside the VIEWER'S RIGHT ear. Keep the silver-white high collar and white sleeveless/shoulder-cutout fantasy clothing with delicate silver trim visible in the head-and-upper-torso crop. Preserve small white dragon wings behind her shoulders; a short white scaly dragon-tail curve may appear at the edge if space permits. Calm kind subtle smile, composed personality. No mint green palette, no book. Match the reference character exactly, using simple outlined shapes and pale lilac shadow colors rather than excessive rendering.
```
