# 妄想天使组合：立绘与 Q 版资产

## 茶话会视觉主题（2026-10-16）

背景 `tea-party-reference.jpg` 原样复制用户提供的 `148951528_p0.jpg`，不重绘人物，不修改原始文件。页面仅通过 CSS 裁切位置和底部渐变适配桌面与手机；聊天正文另有浅色底衬。

`web/tea-theme.css` 以粉红为茶话会主映像色，搭配奶白底色，薄荷青仅用于少量点缀。主题以 `data-room-id="zzz-trio"` 限定，避免覆盖往生堂的暖棕色房间。`web/favicon.svg` 为页面自绘矢量装饰，使用柔粉渐变底、淡玫粉外框、奶白羽翼与深粉星芒，保留薄荷色光环作为点缀，不作为官方标识。

## 南宫羽动作修订（最终采用）

用户要求立绘动作与另外两人区别更明显。将南宫羽改为双臂交叉、轻微侧身、单侧重心的站姿，保留服装、头顶横环与自身左腿红宽腿环。头像保持首批版本。

编辑参考：首批南宫羽立绘 `exec-dfd40132-19c6-406c-9aa7-6a8ede3162aa.png`。最终图片直接复制至 `web/assets/zzz-nangong-yu-stand.png`，未作程序化图像修改。

内置工具，`transparent_background: true`，完整最终提示词：

```text
Use case: identity-preserve. Asset type: transparent full-body character standing illustration for a chat room. Edit target: Image 1, the current Nangong Yu (南宫羽) full-body anime illustration. User request: change her pose so she is visually distinct from the two companions' open-arm welcoming poses. Change pose only: she stands at a gentle three-quarter angle, BOTH ARMS comfortably FOLDED across her upper waist/chest (clearly recognizable crossed-arm stance), shoulders relaxed, body weight resting on her own right leg; her own left knee softly bent, foot placed a small step to the side. A small head tilt and a confident, warm, knowing closed-mouth smile, looking toward the viewer, fitting a perceptive relaxed team leader. NOT a forward-reaching palm, NOT a hand raised beside her face, NOT a peace sign. Preserve character identity and the same clean anime linework, restrained cel shading, proportions and palette from Image 1. Exact appearance invariants: black blunt bangs with puffy side curls ending coral pink; coral petal head decorations, NOT animal ears; red eyes; thin mint horizontal floating halo ABOVE her head; silver-white fitted short dress with coral dotted center and black/red bands; mint neck bow; detached black sleeves with large black feather cuffs; silver-white wing/blade ornaments; black thigh-high stockings with zigzag tops and coral diamond motifs; the wide red thigh band belongs to her OWN LEFT thigh; silver-white open-toe chunky heels with ankle feathers and mint bows. Do not swap left and right or redesign the clothes; show both shoes and all head ornaments completely. Keep the original character's costume coverage. No new accessories, no other characters, no text. Isolated full-body portrait on genuinely transparent background, clean alpha all around character and between limbs; no backdrop, no fog, no glow, no ground shadow, no vignette. Slight clear margin above halo and below shoes. One finished portrait PNG.
```


日期：2026-10-13。

使用技能：`~/.codex/skills\zzz-trio-reference\SKILL.md` 和内置 imagegen 技能。生成前已读取三人的视觉档案、三人差异与提示词、素材来源与模型记录，并实际查看三张三视图。爱芮使用人形外观。

## 生成工具与素材来源

使用内置 `image_gen.imagegen`，首批 6 张素材各独立调用一次；`transparent_background: true`。首批每次提供两张参考：第一张为相应角色三视图，第二张只用于画风。随后按用户要求再次编辑南宫羽的立绘动作，最终动作版见“南宫羽动作修订（最终采用）”。未使用 CLI，未用代码重绘、抠图、裁切、缩放或修改 PNG。

角色原作为《绝区零》，本次图片为依据用户提供参考图的 AI 辅助同人重绘，不作为官方图发布。角色三视图来自用户于 2026-10-13 提供并由技能原样留存的素材：

| 角色 | 用户原文件名 | 技能留存三视图 |
| --- | --- | --- |
| 千夏 / Sunna | 千夏三视图设定稿.png | `assets/reference-images/sunna-turnaround.png` |
| 南宫羽 / Nangong Yu | 南宫羽三视图.png | `assets/reference-images/nangong-yu-turnaround.png` |
| 爱芮 / Aria（人形） | 爱芮三视图.png | `assets/reference-images/aria-human-turnaround.png` |

以上路径以 `~/.codex/skills\zzz-trio-reference` 为根目录。参考 PNG 的原作者及官方出版状态未从文件名确认。技能来源记录中，配套模型包声明“模型制作：观海子”；本次没有加载、修改或渲染模型，不把该模型声明转作这些 AI 图片的作者署名。原始参考资料未改写。

画风参考来自项目内用户提供的 `web/assets/deepseek-original.jpg`（立绘）与用户参考图重绘的 `web/assets/deepseek-avatar-reference.png`（Q 版）。它们只控制清楚线稿、平涂和简洁赛璐璐阴影，人物身份不从这两张借用。

## 最终文件映射

首批生成原图目录：`~/.codex/generated_images\01a13545-d5c6-7782-b287-96effd1fc1e4`。南宫羽动作修订版使用下表中的独立绝对路径。

| 项目文件 | 工具生成原文件 | 尺寸 | 透明区域抽样比例 |
| --- | --- | --- | --- |
| `zzz-sunna-stand.png` | `exec-f9ac0041-e2e1-4483-b9d0-a4caa2ebbd78.png` | 1024 × 1536 | 69.64% |
| `zzz-sunna-avatar.png` | `exec-b9f420e6-3ae4-4244-a836-6774bc5fb7f6.png` | 1254 × 1254 | 30.28% |
| `zzz-nangong-yu-stand.png` | `~/.codex/generated_images/01a13541-f1a7-7990-b0d6-25d98e4282e7/exec-8b8be19d-5b2d-438f-b212-f17fcdc715f3.png` | 1024 × 1536 | 动作修订版，实际透明显示 |
| `zzz-nangong-yu-avatar.png` | `exec-870fc7cf-27ac-4d9a-8061-7019a7e93341.png` | 1254 × 1254 | 32.88% |
| `zzz-aria-stand.png` | `exec-adab9b0f-8363-4b12-b161-c5b2f0223f30.png` | 1024 × 1536 | 67.68% |
| `zzz-aria-avatar.png` | `exec-801aec2b-c948-47f5-96a4-3d7ef524115d.png` | 1254 × 1254 | 26.64% |

项目路径均为当前 `web/assets/` 下的对应文件。最终 PNG 为上述生成原图的原样复制。千夏使用首版立绘；另一次背景修正尝试未被选用，不属于最终交付。

## 视觉与透明检查

- 千夏：浅鼠尾草绿及肩发，自身左侧大青结位于正面画面右；自身右腿的白色镂空长袜与粉色腿包位于画面左，自身左腿黑带位于画面右。红领带、黑色尖瓣裙、粉白横条纹与粉色厚底鞋保留。背包后部标牌在当前正面姿势下被遮挡，没有移到胸前。
- 南宫羽：黑发珊瑚粉卷梢，头顶近水平青绿悬环；黑色大羽簇袖口、黑长袜、白银露趾鞋保留。红宽腿环在自身左腿，即正面画面右，没有镜像。
- 爱芮：人形面部与四肢，粉发青绿挑染、上二束加下二束；橙环耳机与后脑竖直四尖环分清。橙色后腰飘带、青绿裙侧圆形组件、粉色竖纹袜及白靴保留，没有机器人形态或他人的腿饰。
- 三张立绘均完整呈现头饰、腿饰和鞋；三张 Q 版均为大头小上半身的方形头像，保持各自配色和头饰。
- 六张均为带真实 alpha 的 32 位 PNG，边角 alpha 为 0。使用 System.Drawing 只读读取像素与尺寸；抽样透明比例仅用于检查，不是逐像素分割评估。
- **透明区 RGB 与工具预览的差异**：部分立绘的透明像素仍保存灰雾或彩色 RGB，但它们的 alpha 为 0，不属于半透明背景。忽略 alpha 的黑底预览会显示这些 RGB。例如千夏 (200,1200) 为 RGB 69/47/54、A=0；南宫羽 (850,1400) 为 RGB 72/72/77、A=0；爱芮 (850,1400) 为 RGB 119/122/130、A=0。正常浏览器合成时这些像素完全不可见，不能仅凭这种预览再次抠图。
- 主任务已完成浏览器验收：六张图片全部加载、实际透明且无雾，无 JavaScript 错误或横向溢出。页面截图保存在 `.tavern/zzz-preview.jpg`。

## 完整生成提示词

### zzz-sunna-stand.png

身份参考：`~/.codex/skills/zzz-trio-reference/assets/reference-images/sunna-turnaround.png`

画风参考：`./web/assets/deepseek-original.jpg`

```text
Use case: stylized-concept.
Create exactly ONE illustration of the character from image 1. Image 1 is the authoritative character identity and outfit turnaround reference. Image 2 is STYLE ONLY: borrow its clean outlined Japanese anime drawing and restrained flat cel shading, but copy absolutely none of its hair, ears, face, costume, accessories, props, or species.
Style: clean precise dark-colored anime line art, readable separated flat color shapes, only two or three restrained cel-shading layers, minimal gradients, no oily highlights, no heavy makeup, no photoreal rendering, no painterly texture, no micro-detailed hair strands, no bloom or glow filters. Friendly natural expression, wholesome relaxed pose with no sexual emphasis. Follow the original outfit and identity from image 1.
Background: genuine transparent PNG alpha. No scene, floor, ground shadow, vignette, color backdrop, atmospheric glow, frame, border, checkerboard or extra people. Do not reproduce the turnaround sheet, multiple views, headings, watermarks or captions. Preserve tiny existing outfit insignia only as supported by the reference; do not invent text.
Laterality: all anatomical left/right directions below refer to the CHARACTER herself. In a front-facing image, her own right appears on the viewer's LEFT; her own left appears on the viewer's RIGHT. Never mirror the asymmetric accessories.
Character: Sunna / 千夏 from Zenless Zone Zero, faithful to image 1.
Pale muted sage-green shoulder-length loose wavy hair with outward curls, turquoise-teal eyes, a single high side tuft tied by a large mint-teal pointed bow on HER OWN LEFT (viewer RIGHT). Keep the small black hollow-triangle clip near the central bangs and two tiny black hair clips toward her own left. No twin tails, no ahoge, no animal ears, no halo. Black thin choker with small metal studs.
White collared puff-sleeve shirt with pointed lower hem, bright RED long necktie with small white motifs, pink backpack shoulder straps. Black voluminous layered pointed-petal short skirt, distinct dense overlapping pointed petals rather than pleats. Teal polka-dot bow-like ornament with small yellow/orange round center at HER OWN RIGHT front waist (viewer LEFT). White pointed wing-like pieces beside the pink rigid rectangular rotary-dial-style backpack. If its rear label is visible it reads exactly 314; do not move the rear label to her chest.
Both forearms have loose pink-and-white HORIZONTAL striped warmers. Both lower legs have loose bunchy pink-and-white HORIZONTAL striped leg warmers. Critical leg asymmetry: HER OWN RIGHT leg (viewer LEFT) has the white long stocking with oval cutouts plus the pink double thigh straps and small outer thigh pouch. HER OWN LEFT leg (viewer RIGHT) has bare thigh/knee area and two black bands above the leg warmer with a small teal side bow; no corresponding white long stocking or pouch on this left leg. Pink round-toe platform shoes with silver-gray strapped hardware and segmented silver-gray soles. Preserve both complete shoes.
Output framing: vertical portrait full-body game standing illustration, approximately 1024 by 1536. Exactly one whole character centered, entire head ornaments/rings, all hands, skirt layers, leg accessories and shoes comfortably inside frame with 6–8 percent transparent margin. Normal reference-like anime proportions, not chibi. Gentle relaxed mostly front-facing pose with only a slight three-quarter turn; legs separated rather than crossed so their correct asymmetric accessories remain readable. A small natural greeting gesture is fine. Do not force hidden rear details onto the front.
```

### zzz-sunna-avatar.png

身份参考：`~/.codex/skills/zzz-trio-reference/assets/reference-images/sunna-turnaround.png`

画风参考：`./web/assets/deepseek-avatar-reference.png`

```text
Use case: stylized-concept.
Create exactly ONE illustration of the character from image 1. Image 1 is the authoritative character identity and outfit turnaround reference. Image 2 is STYLE ONLY: borrow its clean outlined Japanese anime drawing and restrained flat cel shading, but copy absolutely none of its hair, ears, face, costume, accessories, props, or species.
Style: clean precise dark-colored anime line art, readable separated flat color shapes, only two or three restrained cel-shading layers, minimal gradients, no oily highlights, no heavy makeup, no photoreal rendering, no painterly texture, no micro-detailed hair strands, no bloom or glow filters. Friendly natural expression, wholesome relaxed pose with no sexual emphasis. Follow the original outfit and identity from image 1.
Background: genuine transparent PNG alpha. No scene, floor, ground shadow, vignette, color backdrop, atmospheric glow, frame, border, checkerboard or extra people. Do not reproduce the turnaround sheet, multiple views, headings, watermarks or captions. Preserve tiny existing outfit insignia only as supported by the reference; do not invent text.
Laterality: all anatomical left/right directions below refer to the CHARACTER herself. In a front-facing image, her own right appears on the viewer's LEFT; her own left appears on the viewer's RIGHT. Never mirror the asymmetric accessories.
Character: Sunna / 千夏 from Zenless Zone Zero, faithful to image 1.
Pale muted sage-green shoulder-length loose wavy hair with outward curls, turquoise-teal eyes, a single high side tuft tied by a large mint-teal pointed bow on HER OWN LEFT (viewer RIGHT). Keep the small black hollow-triangle clip near the central bangs and two tiny black hair clips toward her own left. No twin tails, no ahoge, no animal ears, no halo. Black thin choker with small metal studs.
White collared puff-sleeve shirt with pointed lower hem, bright RED long necktie with small white motifs, pink backpack shoulder straps. Black voluminous layered pointed-petal short skirt, distinct dense overlapping pointed petals rather than pleats. Teal polka-dot bow-like ornament with small yellow/orange round center at HER OWN RIGHT front waist (viewer LEFT). White pointed wing-like pieces beside the pink rigid rectangular rotary-dial-style backpack. If its rear label is visible it reads exactly 314; do not move the rear label to her chest.
Both forearms have loose pink-and-white HORIZONTAL striped warmers. Both lower legs have loose bunchy pink-and-white HORIZONTAL striped leg warmers. Critical leg asymmetry: HER OWN RIGHT leg (viewer LEFT) has the white long stocking with oval cutouts plus the pink double thigh straps and small outer thigh pouch. HER OWN LEFT leg (viewer RIGHT) has bare thigh/knee area and two black bands above the leg warmer with a small teal side bow; no corresponding white long stocking or pouch on this left leg. Pink round-toe platform shoes with silver-gray strapped hardware and segmented silver-gray soles. Preserve both complete shoes.
Output framing: square 1:1 chibi head-and-upper-body chat avatar, approximately 1024 by 1024. Exactly one large cute head, small shoulders/upper torso, head occupying about 65–70 percent of character height. Eyes and face large and readable at small sizes, friendly mild smile. All head ornaments, hair bows, hair bunches and any ring fit completely within the square with a small transparent margin. Preserve distinctive shoulder/collar/sleeve features that enter the crop. This is an upper-body crop, so do not squeeze a full pair of legs or tiny full body into the avatar. Use simpler, slightly thicker line art and broad flat cel-shaded shapes like image 2, not ornate glossy rendering.
```

### zzz-nangong-yu-stand.png

身份参考：`~/.codex/skills/zzz-trio-reference/assets/reference-images/nangong-yu-turnaround.png`

画风参考：`./web/assets/deepseek-original.jpg`

```text
Use case: stylized-concept.
Create exactly ONE illustration of the character from image 1. Image 1 is the authoritative character identity and outfit turnaround reference. Image 2 is STYLE ONLY: borrow its clean outlined Japanese anime drawing and restrained flat cel shading, but copy absolutely none of its hair, ears, face, costume, accessories, props, or species.
Style: clean precise dark-colored anime line art, readable separated flat color shapes, only two or three restrained cel-shading layers, minimal gradients, no oily highlights, no heavy makeup, no photoreal rendering, no painterly texture, no micro-detailed hair strands, no bloom or glow filters. Friendly natural expression, wholesome relaxed pose with no sexual emphasis. Follow the original outfit and identity from image 1.
Background: genuine transparent PNG alpha. No scene, floor, ground shadow, vignette, color backdrop, atmospheric glow, frame, border, checkerboard or extra people. Do not reproduce the turnaround sheet, multiple views, headings, watermarks or captions. Preserve tiny existing outfit insignia only as supported by the reference; do not invent text.
Laterality: all anatomical left/right directions below refer to the CHARACTER herself. In a front-facing image, her own right appears on the viewer's LEFT; her own left appears on the viewer's RIGHT. Never mirror the asymmetric accessories.
Character: Nangong Yu / 南宫羽 from Zenless Zone Zero, faithful to image 1.
Black bangs, twin fluffy side hair bunches ending in layered curled CORAL-PINK tips, not ordinary long straight ponytails. Coral petal ornaments and little teal ribbon/leaf decorations near the side hair, not animal ears. Warm pink-red irises. One thin TEAL ring floats HORIZONTALLY above the head, appearing as a flattened pointed ellipse from the front. It is not a vertical ring behind the head.
Silver-white corseted fitted upper outfit with vertical seams, exposed shoulders, black choker and small white upright collar, mint-teal throat bow. Coral dotted chest panels and a narrow coral central strip crossed by dark details. Small triangular midriff opening matching the reference. Short flared silver-white pointed-petal skirt pieces over black and coral-red frills. Separate long BLACK sleeves with coral upper ruffles, huge dense BLACK pointed-feather clusters around each wrist, little teal bows. Silver-white segmented blade/wing-like ornaments with round joints spread behind the arms.
Both legs have coral lattice trim high on thighs, small exposed skin band, then BLACK thigh-high stockings with jagged tops. Critical asymmetry: the wide RED band with silver studs belongs ONLY to HER OWN LEFT thigh (viewer RIGHT), never to the opposite leg. Black pointed-feather ankle clusters with teal bows. Silver-white open-toe multiple-strap platform sandals with pale SILVER-WHITE chunky heels and soles, visible toes; do not replace them with black soles, boots, or closed-toe shoes.
Output framing: vertical portrait full-body game standing illustration, approximately 1024 by 1536. Exactly one whole character centered, entire head ornaments/rings, all hands, skirt layers, leg accessories and shoes comfortably inside frame with 6–8 percent transparent margin. Normal reference-like anime proportions, not chibi. Gentle relaxed mostly front-facing pose with only a slight three-quarter turn; legs separated rather than crossed so their correct asymmetric accessories remain readable. A small natural greeting gesture is fine. Do not force hidden rear details onto the front.
```

### zzz-nangong-yu-avatar.png

身份参考：`~/.codex/skills/zzz-trio-reference/assets/reference-images/nangong-yu-turnaround.png`

画风参考：`./web/assets/deepseek-avatar-reference.png`

```text
Use case: stylized-concept.
Create exactly ONE illustration of the character from image 1. Image 1 is the authoritative character identity and outfit turnaround reference. Image 2 is STYLE ONLY: borrow its clean outlined Japanese anime drawing and restrained flat cel shading, but copy absolutely none of its hair, ears, face, costume, accessories, props, or species.
Style: clean precise dark-colored anime line art, readable separated flat color shapes, only two or three restrained cel-shading layers, minimal gradients, no oily highlights, no heavy makeup, no photoreal rendering, no painterly texture, no micro-detailed hair strands, no bloom or glow filters. Friendly natural expression, wholesome relaxed pose with no sexual emphasis. Follow the original outfit and identity from image 1.
Background: genuine transparent PNG alpha. No scene, floor, ground shadow, vignette, color backdrop, atmospheric glow, frame, border, checkerboard or extra people. Do not reproduce the turnaround sheet, multiple views, headings, watermarks or captions. Preserve tiny existing outfit insignia only as supported by the reference; do not invent text.
Laterality: all anatomical left/right directions below refer to the CHARACTER herself. In a front-facing image, her own right appears on the viewer's LEFT; her own left appears on the viewer's RIGHT. Never mirror the asymmetric accessories.
Character: Nangong Yu / 南宫羽 from Zenless Zone Zero, faithful to image 1.
Black bangs, twin fluffy side hair bunches ending in layered curled CORAL-PINK tips, not ordinary long straight ponytails. Coral petal ornaments and little teal ribbon/leaf decorations near the side hair, not animal ears. Warm pink-red irises. One thin TEAL ring floats HORIZONTALLY above the head, appearing as a flattened pointed ellipse from the front. It is not a vertical ring behind the head.
Silver-white corseted fitted upper outfit with vertical seams, exposed shoulders, black choker and small white upright collar, mint-teal throat bow. Coral dotted chest panels and a narrow coral central strip crossed by dark details. Small triangular midriff opening matching the reference. Short flared silver-white pointed-petal skirt pieces over black and coral-red frills. Separate long BLACK sleeves with coral upper ruffles, huge dense BLACK pointed-feather clusters around each wrist, little teal bows. Silver-white segmented blade/wing-like ornaments with round joints spread behind the arms.
Both legs have coral lattice trim high on thighs, small exposed skin band, then BLACK thigh-high stockings with jagged tops. Critical asymmetry: the wide RED band with silver studs belongs ONLY to HER OWN LEFT thigh (viewer RIGHT), never to the opposite leg. Black pointed-feather ankle clusters with teal bows. Silver-white open-toe multiple-strap platform sandals with pale SILVER-WHITE chunky heels and soles, visible toes; do not replace them with black soles, boots, or closed-toe shoes.
Output framing: square 1:1 chibi head-and-upper-body chat avatar, approximately 1024 by 1024. Exactly one large cute head, small shoulders/upper torso, head occupying about 65–70 percent of character height. Eyes and face large and readable at small sizes, friendly mild smile. All head ornaments, hair bows, hair bunches and any ring fit completely within the square with a small transparent margin. Preserve distinctive shoulder/collar/sleeve features that enter the crop. This is an upper-body crop, so do not squeeze a full pair of legs or tiny full body into the avatar. Use simpler, slightly thicker line art and broad flat cel-shaded shapes like image 2, not ornate glossy rendering.
```

### zzz-aria-stand.png

身份参考：`~/.codex/skills/zzz-trio-reference/assets/reference-images/aria-human-turnaround.png`

画风参考：`./web/assets/deepseek-original.jpg`

```text
Use case: stylized-concept.
Create exactly ONE illustration of the character from image 1. Image 1 is the authoritative character identity and outfit turnaround reference. Image 2 is STYLE ONLY: borrow its clean outlined Japanese anime drawing and restrained flat cel shading, but copy absolutely none of its hair, ears, face, costume, accessories, props, or species.
Style: clean precise dark-colored anime line art, readable separated flat color shapes, only two or three restrained cel-shading layers, minimal gradients, no oily highlights, no heavy makeup, no photoreal rendering, no painterly texture, no micro-detailed hair strands, no bloom or glow filters. Friendly natural expression, wholesome relaxed pose with no sexual emphasis. Follow the original outfit and identity from image 1.
Background: genuine transparent PNG alpha. No scene, floor, ground shadow, vignette, color backdrop, atmospheric glow, frame, border, checkerboard or extra people. Do not reproduce the turnaround sheet, multiple views, headings, watermarks or captions. Preserve tiny existing outfit insignia only as supported by the reference; do not invent text.
Laterality: all anatomical left/right directions below refer to the CHARACTER herself. In a front-facing image, her own right appears on the viewer's LEFT; her own left appears on the viewer's RIGHT. Never mirror the asymmetric accessories.
Character: Aria / 爱芮 HUMAN APPEARANCE from Zenless Zone Zero, exactly the human reference image 1, no robot variant.
Warm coral-pink hair with teal streak down the curved central fringe and teal streaks in lower hair. Precisely FOUR major side hair bunches: upper pair fluffy and flaring UP/outward, lower pair shoulder-length and curling OUTward. Black geometric hair ties. Do not reduce to ordinary twin tails or round buns. Black/dark-gray headphones with ORANGE ring ear cups and thin upward angled dark headphone pieces, NOT animal ears.
A substantial teal open ring with FOUR pointed extensions sits VERTICALLY BEHIND THE BACK OF THE HEAD, with visible depth; it is not a horizontal floating halo above her head. Front view shows portions of the teal ring around the hair. Both eyes have a similar lively multicolored teal-blue-purple-pink appearance, not mismatched solid eyes. Human face, arms, hands and legs without mechanical seams.
White high collar, orange crossed pointed chest ribbons, white fitted bodice with narrow black vertical center line and short puff sleeves. Flared white segmented skirt with small black lower motif and thin black edging, teal frill plus white lace hem. Large teal faceted hard components at each skirt side with pale/black/orange circular speaker-like faces. Silver-white pointed wing-like pieces behind shoulders, distinct from the skirt components.
An orange large bow at the BACK WAIST with TWO wide long forked ribbon tails, not an animal tail. Silver-white pointed wrist guards with teal details, pink fingerless gloves. Both bare knees and thighs; paired PINK mid-calf socks with pale VERTICAL ribs, small white ruffled tops and teal bows. WHITE lace-up chunky-heeled ankle boots with large folded cuffs, teal laces/bows, small orange front diamond panels. Do not add black thigh-high stockings or asymmetric leg pouches.
Output framing: vertical portrait full-body game standing illustration, approximately 1024 by 1536. Exactly one whole character centered, entire head ornaments/rings, all hands, skirt layers, leg accessories and shoes comfortably inside frame with 6–8 percent transparent margin. Normal reference-like anime proportions, not chibi. Gentle relaxed mostly front-facing pose with only a slight three-quarter turn; legs separated rather than crossed so their correct asymmetric accessories remain readable. A small natural greeting gesture is fine. Do not force hidden rear details onto the front.
```

### zzz-aria-avatar.png

身份参考：`~/.codex/skills/zzz-trio-reference/assets/reference-images/aria-human-turnaround.png`

画风参考：`./web/assets/deepseek-avatar-reference.png`

```text
Use case: stylized-concept.
Create exactly ONE illustration of the character from image 1. Image 1 is the authoritative character identity and outfit turnaround reference. Image 2 is STYLE ONLY: borrow its clean outlined Japanese anime drawing and restrained flat cel shading, but copy absolutely none of its hair, ears, face, costume, accessories, props, or species.
Style: clean precise dark-colored anime line art, readable separated flat color shapes, only two or three restrained cel-shading layers, minimal gradients, no oily highlights, no heavy makeup, no photoreal rendering, no painterly texture, no micro-detailed hair strands, no bloom or glow filters. Friendly natural expression, wholesome relaxed pose with no sexual emphasis. Follow the original outfit and identity from image 1.
Background: genuine transparent PNG alpha. No scene, floor, ground shadow, vignette, color backdrop, atmospheric glow, frame, border, checkerboard or extra people. Do not reproduce the turnaround sheet, multiple views, headings, watermarks or captions. Preserve tiny existing outfit insignia only as supported by the reference; do not invent text.
Laterality: all anatomical left/right directions below refer to the CHARACTER herself. In a front-facing image, her own right appears on the viewer's LEFT; her own left appears on the viewer's RIGHT. Never mirror the asymmetric accessories.
Character: Aria / 爱芮 HUMAN APPEARANCE from Zenless Zone Zero, exactly the human reference image 1, no robot variant.
Warm coral-pink hair with teal streak down the curved central fringe and teal streaks in lower hair. Precisely FOUR major side hair bunches: upper pair fluffy and flaring UP/outward, lower pair shoulder-length and curling OUTward. Black geometric hair ties. Do not reduce to ordinary twin tails or round buns. Black/dark-gray headphones with ORANGE ring ear cups and thin upward angled dark headphone pieces, NOT animal ears.
A substantial teal open ring with FOUR pointed extensions sits VERTICALLY BEHIND THE BACK OF THE HEAD, with visible depth; it is not a horizontal floating halo above her head. Front view shows portions of the teal ring around the hair. Both eyes have a similar lively multicolored teal-blue-purple-pink appearance, not mismatched solid eyes. Human face, arms, hands and legs without mechanical seams.
White high collar, orange crossed pointed chest ribbons, white fitted bodice with narrow black vertical center line and short puff sleeves. Flared white segmented skirt with small black lower motif and thin black edging, teal frill plus white lace hem. Large teal faceted hard components at each skirt side with pale/black/orange circular speaker-like faces. Silver-white pointed wing-like pieces behind shoulders, distinct from the skirt components.
An orange large bow at the BACK WAIST with TWO wide long forked ribbon tails, not an animal tail. Silver-white pointed wrist guards with teal details, pink fingerless gloves. Both bare knees and thighs; paired PINK mid-calf socks with pale VERTICAL ribs, small white ruffled tops and teal bows. WHITE lace-up chunky-heeled ankle boots with large folded cuffs, teal laces/bows, small orange front diamond panels. Do not add black thigh-high stockings or asymmetric leg pouches.
Output framing: square 1:1 chibi head-and-upper-body chat avatar, approximately 1024 by 1024. Exactly one large cute head, small shoulders/upper torso, head occupying about 65–70 percent of character height. Eyes and face large and readable at small sizes, friendly mild smile. All head ornaments, hair bows, hair bunches and any ring fit completely within the square with a small transparent margin. Preserve distinctive shoulder/collar/sleeve features that enter the crop. This is an upper-body crop, so do not squeeze a full pair of legs or tiny full body into the avatar. Use simpler, slightly thicker line art and broad flat cel-shaded shapes like image 2, not ornate glossy rendering.
```
