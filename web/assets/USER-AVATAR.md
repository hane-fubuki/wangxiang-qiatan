# 羽吹雪的 Q 版用户头像

日期：2026-10-13。

来源：用户在当前任务指定的 ChatGPT 对话《羽吹雪本雪》，conversation ID `6ace46e7-d12c-83ee-a4ec-dc3e820bfd44`。通过 read_thread 读取用户保存的外观描述：深灰色齐腰长发、白色挑染、遮眼刘海、慵懒神情、轻微黑眼圈、白皙肤色、颈挂耳机、宽松滑肩棒球衫与 T 恤。该对话称资料已存为“羽吹雪的默认形象”skill，但本次未能读取云端 SKILL.md、原立绘或三视图；不声称已逐图核对这些文件。

生成方式：内置 `image_gen.imagegen`，`transparent_background: true`。按用户最新要求，放弃旧头像编辑，依据文字提示从头生成，最终调用没有引用旧头像或其他图片。双手完全缩入宽大袖口，不露手指。头像采用上半身构图，腿部不入画，未推断单侧黑丝的左右。衣服及耳机的灰黑配色、灰眼睛是文字未指定部分的低饱和补充。

最终文件：`./web/assets/user-avatar.png`。
原始生成文件：`~/.codex/generated_images/01a13541-f1a7-7990-b0d6-25d98e4282e7/exec-1ff7af3c-b775-4a06-8169-fe3fe3e13036.png`。

最终文件为原生成 PNG 的直接复制，无程序化重绘或裁切。用于所有聊天室的用户消息与左下角用户入口。

2026-10-14 修复页面沿用旧头像的问题：bootstrap 返回带文件内容摘要版本号的图片 URL，替换图片后会使用新 URL 加载。当前最终图片 SHA256 为 `a1a4d9472a9a30b54682b22f661e8a91da3b5ffb272f6fbef66d08ad93eec6a1`。

## 完整提示词

```text
Use case: stylized-concept. Generate from scratch exactly ONE square transparent chibi chat avatar of the user's established anime persona 羽吹雪 (Yubuki), using this character specification. This is a fresh illustration, not an edit of an existing avatar. Identity: waist-length dark charcoal-gray hair with a few distinct WHITE highlighted strands, heavy tousled long bangs nearly concealing the eyes, relaxed sleepy expression with half-lidded muted gray eyes, very subtle under-eye shadows, unusually pale skin. A small quiet smile, gently tilted head, casual slouch. Large black/gray over-ear headphones with small silver details hang around the NECK, not on top of the head. An obviously oversized loose charcoal-and-off-white baseball-style jacket slips from one shoulder over a casual white T-shirt. Cute large-head/small-upper-torso chibi proportions and a softly androgynous face without heavy makeup. POSE REQUIREMENT: both hands are pulled completely inside the jacket's long oversized sleeves. The arms rest loosely near the upper torso in a cozy relaxed pose; the empty cuffs droop/fold naturally. There is absolutely NO visible hand skin, no fingers, no fingertips, no nails, no knuckles, no finger-like folds, no gloves or mittens. Do not place a hand against the cheek. Make this unambiguous: all exposed skin is only face, neck and the small slipped-shoulder area. Composition: a single large centered head and upper body in a square avatar, face clear at thumbnail sizes, complete top and sides of hair with a small transparent margin; long hair may continue naturally out through the bottom crop. No legs shown, therefore do not infer the side of the persona's single black thigh-high stocking. Style: clean hand-drawn Japanese anime outlines with subtle line variation, broad matte flat color shapes, restrained two-to-three-tone cel shading, readable white hair streaks, minimal gradients and rendering, no oily highlights or painterly blur. Background genuinely transparent PNG with clean alpha; no backdrop, glow, shadow, fog, frame or extra objects. No text, logo, animal ears, horns, halo, bow or jewelry.
```
