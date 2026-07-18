# 🎧 AB Blind Audio Test

**一款科学化的音频盲听比对工具，用于评估不同编码格式/码率之间的可听差异。**

> 你相信自己能盲听出 128kbps MP3 和 FLAC 的区别吗？
> 用数据说话，而不是靠心理暗示。

⚡ 本项目由 **Vibe Coding** 完成——人类提出需求、评估方向、检验结果，AI 负责实现。纯人机协作产物。

---

## ✨ 功能详解与使用说明

### 🧪 模式一：AB 盲听

两首音频随机分配 A/B 标签，按 `Space` 即时切换比对，播放结束后揭晓对应关系。

**操作流程：**
1. 点击两个文件卡片，分别加载两首音频
2. 按 `P` 或点击「播放」开始
3. 播放过程中按 `Space` 或点击「切换」在 A/B 之间即时切换
4. 可随时按 `←` `→` 进退 5 秒反复比对片段
5. 播放结束后自动揭晓 A/B 对应的原始文件
6. 可在播放中随时点击「🔒 揭晓」提前看答案
7. 点击「⟳ 重置」停止播放、打乱 A/B 分配、进度归零

---

### 🔍 模式二：差异听取（反相抵消）

将两轨反相相加，同相部分互相抵消，只保留编码损失。配合增益滑块放大微弱差异。

**操作流程：**
1. 加载两首音频后切换到「差异听取」模式
2. 系统自动完成**互相关对齐** + **反相抵消**，渲染差异信号
3. 点击「播放差异」听取纯编码损失
4. 拖动「差异增益」滑块（默认 +6dB）放大细微失真
5. 差异波形图实时显示

**能听到什么：**
- 完全静音 → 两轨编码完全一致（不可能）
- 沙沙噪声 / 高频嘶嘶 → MP3 的量化噪声与 pre-echo
- 空洞感、高频泛音缺失 → MP3 的 18kHz+ 截断
- 不该有声音的地方出现声音 → 编码伪影

---

### 🎯 模式三：ABX 多轮统计

经典心理声学双盲测试。系统随机选定 X=A 或 X=B，用户在未知条件下聆听并判断 X 的归属。10 轮后执行**二项检验（binomial test）**计算 p 值，客观结论。

**操作流程：**
1. 切换至「ABX 多轮」模式
2. 先点听 A/B 熟悉两轨差异，再点 X 判断
3. 三个播放按钮支持**无缝切换** + **同轨暂停**
   - 第一次按某轨 → 从当前位置开始播放
   - 切换到另一轨 → 新轨从**同一位置**继续播
   - 再按同一轨 → 暂停，位置保留
4. 听够后点击「🇦 A」或「🇧 B」投票
5. 系统反馈 ✅ 正确 / ❌ 不对，1.2 秒后自动进入下一轮
6. 顶部圆点标记每轮结果（🟢 正确 / 🔴 错误）
7. 10 轮完成后显示统计面板，含 p 值与结论

---

### 快捷键

| 按键 | 功能 |
|---|---|
| `P` | 播放 / 暂停 |
| `Space` | AB 盲听：切换 A ↔ B |
| `←` `→` | 进退 5 秒 |
| `R` | 重播 |
| `⟳` 重置按钮 | 停止 + 打乱 + 归零 |
| `?` | 显示全部快捷键 |

---

## 📷 截图

<!-- 将截图放入 screenshots/ 目录后替换此处 -->
```
screenshots/ab-mode.png         AB 盲听模式
screenshots/diff-mode.png       差异听取模式（含波形图）
screenshots/abx-mode.png        ABX 多轮测试与统计结果
screenshots/shortcuts.png       快捷键一览遮罩
```

---

## 📦 使用方式

### 浏览器（推荐，零依赖）

直接打开 `index.html`，点击文件卡片选择两首音频即可。

```bash
firefox ~/abtest/index.html
```

支持格式：**MP3、FLAC、WAV、OGG**。

> 在 niri 等部分 Wayland compositor 上，文件选择器可能因 `xdg-desktop-portal` 配置无法弹出。此时可使用桥接模式绕过（见下文），或尝试：
> ```bash
> mkdir -p ~/.config/xdg-desktop-portal
> echo -e '[preferred]\ndefault=gtk' > ~/.config/xdg-desktop-portal/portals.conf
> systemctl --user restart xdg-desktop-portal
> ```

### CLI 版本（Python 环境）

```bash
bash setup.sh                      # 一键安装依赖
./abtest.sh song1.flac song2.mp3   # 启动
```

### 桥接模式（备用方案）

```bash
python3 abtest-bridge.py /path/to/your/music/
```

然后在页面点击「从本机服务器加载」→「连接」→ 从列表中选取文件。

---

## 🔬 专业特性

### ✅ RMS 音量平衡（RMS Normalization）

两轨比较前，计算各自的 RMS（均方根）值作为响度指标，对响度较高的一轨做增益衰减，使两者**听觉响度一致**。排除"哪个更响"的误导性因素——盲听史上最大陷阱就是响度差异。

### ✅ 互相关自动对齐（Cross-Correlation Alignment）

不同编码器（LAME MP3 编码器 vs FLAC 原生编码）在文件头部填充不同数量的 padding 样本，直接反相相减会产生因时间错位而非编码损失的噪声。本工具在渲染差异信号前执行**互相关搜索**：以 0.5 秒片段为模板，在 ±0.15 秒范围内扫描两轨的**最大相关偏移量**，然后用 `source.start(0, offsetSec)` 对齐后再做抵消，确保你听到的是纯粹的编码质量差异。

### ✅ ABX 双盲 + 二项检验（ABX Protocol + Binomial Test）

遵循经典心理声学实验设计：ABX 将辨别问题转化为一系列二选一的选择题，消除所有主观偏差。零假设 H₀ 下每轮正确概率为 p = 0.5。N 轮中正确 k 轮及以上的概率为：

$$P(X \geq k) = \sum_{i=k}^{N} \binom{N}{i} \cdot 0.5^N$$

- **p < 0.05** → 显著（✨ 你的耳朵确实能分辨）
- **p ≥ 0.05** → 不显著（无法排除随机猜测）

### ✅ Web Audio API 离线渲染（OfflineAudioContext）

差异信号不通过实时播放链路的失真计算，而是由 `OfflineAudioContext` 在内存中逐帧精确渲染，保证反相抵消的样本级精度。渲染完成后转为普通 AudioBuffer 播放，品质与效率兼得。

---

## 💻 技术栈

### 浏览器版
- **纯前端**，零运行时依赖，单 HTML 约 60KB
- Web Audio API（`AudioContext`、`OfflineAudioContext`、`GainNode`、`BufferSourceNode`）
- 无框架、无构建步骤、无需 npm install

### CLI 版
- Python 3 + `sounddevice` + `soundfile` + `scipy`
- `uv` 虚拟环境隔离

---

## 📚 项目结构

```
abtest/
├── index.html              # 浏览器版主页面
├── abtest.py               # CLI 版盲听工具
├── abtest-bridge.py        # 本地桥接 HTTP 服务器
├── abtest.sh               # CLI 启动脚本
├── setup.sh                # CLI 依赖安装
├── generate-test.sh        # 测试音频生成
├── screenshots/
├── README.md
├── LICENSE
└── .gitignore
```

---

## 📜 许可

[MIT](LICENSE)

---

⚡ 本项目由 **Vibe Coding** 完成。
人类负责提需求、审代码、测功能、定方向；AI 负责写代码、修 bug、读文档、调样式。这是人类与 AI 协作的探索实践。
