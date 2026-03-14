# Code to PDF 项目文档

## 项目概述

Code to PDF 是一个用于生成代码文件的语法高亮 PDF 文档的 Python 脚本。它可以扫描项目目录中的代码文件，生成带有语法高亮、目录和页码的 PDF 文档，方便代码审查、归档和分享。

本项目由CodeX在GPT-5.1-CodeX-Max辅助下构建
## 功能特性

- 支持多种编程语言的语法高亮（Python、C/C++、CUDA 等）
- 自动尊重 .gitignore 文件的过滤规则
- 生成带有目录的 PDF 文档
- 支持中文字体，避免中文显示问题
- 可选择生成单个文件的 PDF 文档
- 自动处理页面布局和分页
- 显示行号，方便代码引用

## 安装

### 依赖项

项目依赖以下 Python 包：

- `pathspec>=0.12` - 用于解析 .gitignore 规则
- `pygments>=2.18` - 用于代码语法高亮
- `reportlab>=4.1` - 用于生成 PDF 文档

### 安装方法

使用 pip 安装依赖：

```bash
pip install -r requirements.txt
```

或者直接安装：

```bash
pip install pathspec>=0.12 pygments>=2.18 reportlab>=4.1
```

## 使用方法

### 基本用法

```bash
python code_to_pdf.py <project_dir> <output_dir>
```

### 可选参数

- `--font /path/to/font.(ttf|ttc)` - 指定用于嵌入的字体文件，建议使用支持中文的字体
- `--cjk-font /path/to/font.(ttf|ttc)` - 可选的仅用于 CJK 字符的字体
- `--split-files` - 同时为每个代码文件生成单独的 PDF 文档
- `--exclude-dir` - 额外排除的目录（相对于项目目录），可多次使用，可用于排除三方库

### 示例

1. 基本用法：
   ```bash
   python code_to_pdf.py /path/to/project /path/to/output
   ```
2. 使用自定义字体：
   ```bash
   python code_to_pdf.py /path/to/project /path/to/output --font /path/to/font.ttf
   ```
3. 生成单独的 PDF 文件：
   ```bash
   python code_to_pdf.py /path/to/project /path/to/output --split-files
   ```
4. 排除特定目录：
   ```bash
   python code_to_pdf.py /path/to/project /path/to/output --exclude-dir build --exclude-dir __pycache__
   ```

## 代码结构

项目主要由一个 Python 文件 `code_to_pdf.py` 组成，包含以下主要函数：

1. `load_gitignored_files()` - 加载并解析 .gitignore 文件，返回未被忽略的文件列表
2. `filter_code_files()` - 过滤出代码文件，并按路径排序
3. `register_font()` - 注册字体
4. `pick_font()` - 选择合适的字体
5. `token_color()` - 将 Pygments 令牌转换为 ReportLab 颜色
6. `is_cjk()` - 判断字符是否为 CJK 字符
7. `split_font_runs()` - 分割字体运行
8. `measure_pages_for_file()` - 估计文件需要的页数
9. `measure_toc_pages()` - 估计目录需要的页数
10. `draw_toc()` - 绘制目录
11. `draw_highlighted_file()` - 绘制高亮显示的文件
12. `build_pdf()` - 构建 PDF 文档
13. `parse_args()` - 解析命令行参数
14. `main()` - 主函数

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
