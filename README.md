# Code to PDF 项目文档

## 项目概述

Code to PDF 是一个用于生成代码文件的语法高亮 PDF 文档的 Python 脚本。它可以扫描项目目录中的代码文件，生成带有语法高亮、目录和页码的 PDF 文档，方便代码审查、归档和分享。

本项目由 CodeX 在 GPT-5.1-CodeX-Max 辅助下构建。

## 功能特性

- 支持多种编程语言的语法高亮（Python、C/C++、CUDA、HTML、CSS、JavaScript、Shell、CMake、Make 等）
- 自动尊重 .gitignore 文件的过滤规则
- 生成带有目录的 PDF 文档
- 支持目录分组显示（按顶层目录分组或平铺列表）
- PDF 内支持超链接导航（点击目录跳转到文件，点击文件头跳转回目录）
- 支持中文字体，避免中文显示问题
- 可选择生成单个文件的 PDF 文档
- 自动处理页面布局和分页
- 显示行号，方便代码引用
- 生成代码统计信息（文件数、代码行数、注释行数、空白行数）
- 支持并行处理，提高生成速度
- 优化的字体处理，支持混合字体渲染

## 安装

### 依赖项

项目依赖以下 Python 包：

- `pathspec>=0.12` - 用于解析 .gitignore 规则
- `pygments>=2.18` - 用于代码语法高亮
- `reportlab>=4.1` - 用于生成 PDF 文档

### 安装方法

使用 pip 安装依赖：

```bash
pip install pathspec>=0.12 pygments>=2.18 reportlab>=4.1
```

## 使用方法

### 基本用法

```bash
python3 code_to_pdf.py <project_dir> <output_dir>
```

### 可选参数

- `--font /path/to/font.(ttf|ttc)` - 指定用于嵌入的字体文件，建议使用支持中文的字体
- `--cjk-font /path/to/font.(ttf|ttc)` - 可选的仅用于 CJK 字符的字体
- `--split-files` - 同时为每个代码文件生成单独的 PDF 文档
- `--exclude-dir` - 额外排除的目录（相对于项目目录），可多次使用，可用于排除三方库
- `--toc-mode {auto,flat,grouped}` - 目录布局模式：
  - `auto`（默认）- 自动选择，当文件数超过 120 或平均深度超过 3 时使用分组模式
  - `flat` - 平铺列表，所有文件按路径排序显示
  - `grouped` - 按顶层目录分组显示
- `--workers N` - 并行处理的工作线程数（0 = 自动，默认）

### 示例

1. 基本用法：
   ```bash
   python3 code_to_pdf.py /path/to/project /path/to/output
   ```
2. 使用自定义字体：
   ```bash
   python3 code_to_pdf.py /path/to/project /path/to/output --font /path/to/font.ttf
   ```
3. 生成单独的 PDF 文件：
   ```bash
   python3 code_to_pdf.py /path/to/project /path/to/output --split-files
   ```
4. 排除特定目录：
   ```bash
   python3 code_to_pdf.py /path/to/project /path/to/output --exclude-dir build --exclude-dir __pycache__
   ```
5. 使用分组目录模式：
   ```bash
   python3 code_to_pdf.py /path/to/project /path/to/output --toc-mode grouped
   ```
6. 使用并行处理：
   ```bash
   python3 code_to_pdf.py /path/to/project /path/to/output --workers 4
   ```

## 代码结构

项目主要由一个 Python 文件 `code_to_pdf.py` 组成，包含实现代码文件扫描、语法高亮、PDF 生成等功能的核心函数。

## 支持的文件类型

脚本支持以下文件类型：

- `.py` - Python
- `.c` - C
- `.cc`, `.cpp`, `.cxx` - C++
- `.h`, `.hpp` - 头文件
- `.cu`, `.cuh` - CUDA
- `.qml` - QML
- `.html`, `.htm` - HTML
- `.js` - JavaScript
- `.jsx` - JSX
- `.css` - CSS
- `.cmake` - CMake
- `.mk` - Makefile
- `.sh` - Shell
- `CMakeLists.txt` - CMake
- `Makefile` - Makefile

## 字体处理

脚本会自动尝试以下字体（按优先级）：

1. 用户通过 `--font` 或 `--cjk-font` 指定的字体
2. 系统中可用的 CJK 字体，如：
   - SarasaMonoSC
   - LXGWWenKaiMono
   - NotoSansMonoCJK
   - PingFang
   - STHeiti Light
   - Arial Unicode
   - SourceHanSansSC
   - NotoSansCJK
   - WQYZenHei
   - WQYMicroHei
   - MicrosoftYaHei
   - SimHei
3. 默认字体 Courier

## 输出结构

生成的 PDF 文件将保存在指定的输出目录中：

- 主 PDF 文件：`<output_dir>/<project_name>.pdf`
- 如果使用 `--split-files` 选项，单独的 PDF 文件将保存在 `<output_dir>/files/` 目录中

## PDF 导航功能

生成的 PDF 支持交互式导航：

- **目录导航**：点击目录中的文件名，可直接跳转到对应的代码文件
- **返回目录**：点击文件头部的路径，可返回目录页面
- **页码显示**：每页底部显示全局页码（如 5/100）

## 代码统计功能

生成的 PDF 包含代码统计信息页面，显示以下内容：

- 每种语言的文件数
- 每种语言的空白行数
- 每种语言的注释行数
- 每种语言的代码行数
- 总计统计信息

统计信息使用表格形式展示，位于 PDF 文档的开头。

## 注意事项

1. 脚本会自动尊重 .gitignore 文件的规则，不会包含被忽略的文件
2. 为了避免中文显示问题，建议使用支持中文的字体
3. 对于大型项目，生成 PDF 可能需要较长时间和较多内存
4. 脚本会尝试自动选择系统中可用的字体，但在某些环境中可能需要手动指定字体

## 故障排除

### 中文字体显示问题

如果中文显示为方块或乱码，请使用 `--font` 参数指定一个支持中文的字体文件。

### 内存错误

对于大型项目，可能会出现内存错误。可以尝试：

1. 排除不必要的目录
2. 不使用 `--split-files` 选项
3. 分批处理项目

### 字体加载错误

如果指定的字体文件无法加载，请确保：

1. 字体文件路径正确
2. 字体文件格式为 TTF 或 TTC
3. 字体文件没有损坏

## 许可证

本项目采用 MIT 许可证。
