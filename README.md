<div align="center">

# PKPM Agent 用户手册

</div>

[**😊许愿池 & ☹️点我吐槽**](https://gitee.com/pkpmgh/PKPMAgentRelease/issues/ICWL5R)

## 1. 基本信息

**✨ PKPM Agent 设计智能体**

是一款基于大语言模型的设计辅助工具。通过自然语言交互的方式，可以实现：
- 🏗️ **结构模型创建与修改**
- 📊 **荷载自动布置**
- 📈 **计算结果查询与可视化**
- 📐 **CAD 自动绘图**

**🌠 使用界面**

<img src="HelpImage/界面.png" alt="工具启动界面" width="600">

## 2. 基本配置(用前必读)

### 2.1 环境
- 💻 **需要安装：PKPM2026R1.0-64 及以上，AutoCAD 2014 及以上(绘图)**
- 🌐 **需连接网络(用于大模型调用)**

### 2.2 启动位置
打开 PKPM 软件，在 **轴网** 菜单栏中点击 **⌈PKPM Agent 尝鲜版⌋**，即可打开Agent对话框，支持页面缩放。

<img src="HelpImage/启动.png" alt="工具启动界面" width="800">

### 2.3 大模型设置

- 在 Agent 面板中点击 "管理" 按钮，从下拉菜单中选择要使用模型：

<img src="HelpImage/模型选择.png" alt="工具启动界面" width="800">

- 然后再点击小齿轮，填入模型服务商的 APIKey：

<img src="HelpImage/apikey.png" alt="工具启动界面" width="800">


- 可以点击 **获取 API 密钥** 直接跳转到对应网页。

<img src="HelpImage/offical.png" alt="工具启动界面" width="800">

我们测试下来感觉 **质谱清言glm-4.5** 是国内性能最强大的模型，也推荐您使用。

**🎁 点击注册即可获取质谱官方送出的20元使用额度。**

## 3. 功能介绍

### 3.1 工具管理

**🛠️ 系统目前内置了近 100 种工具，涵盖建模、截面编辑、荷载添加、构件结果、指标结果、CAD绘制等常用功能**

**⚠️ 注意：关闭某个工具组后，Agent 就会丧失相应的能力，如果发现模型未能完成任务，可以确认工具组是否已开启。** 

- 点击**工具管理**，可以查看Agent目前掌握的所有工具。

<div align="center">
<img src="HelpImage/tools.png" alt="" width="800">
</div>

- 可以控制是否启用相关工具组，**只启用必要的工具组可以提高效率与准确性，大幅降低Token消耗。**

<div align="center">
<img src="HelpImage/Alltools.png" alt="" width="500">
</div>



### 3.2 二次开发

**我们支持用户自定义工具供大模型调用，编写完成后，将会展示在 工具管理-> 用户自定义 页面下**

<img src="HelpImage/二次开发文件路径.png" alt="" width="800">

打开 UserDefineTool.py，编写MCP工具，示例代码如下：
```python
from PKPMMCP.Base import *
__Tag = ToolAnnotations(title = "用户自定义") 

#示例代码
@mcp.tool(annotations=__Tag)
def add(a, b) -> bool:
    """ 加法运算器 """   
    return a + b
```


## 4. 案例
### 4.1 建模
- 提示词：**在选中的柱子顶部连接上主梁，xy 两个方向都形成框架**
- 通过自然语言指令让智能体自动操纵 PKPM 软件，完成模型构件创建、连接关系调整、参数修改等任务，支持梁柱、标准层等操作。

<img src="HelpImage/建模.gif" alt="" width="1200">

### 4.2 荷载布置
- 提示词：**粘贴提资后，要求施加荷载**
- 支持读取 Excel 格式的上游提资数据（如恒载、活载数值及坐标），自动完成楼层、节点的荷载布置，减少手动输入错误。

<img src="HelpImage/荷载.gif" alt="" width="1200">

### 4.3 查询计算结果
- 提示词：**获取选中柱子的轴压比，绘制直方图**
- 通过自然语言指令查询结构计算结果（如轴压比、位移角等），并自动生成直方图、曲线等可视化图表，无需手动导出数据后二次处理。

<img src="HelpImage/后处理.gif" alt="" width="1200">

### 4.4 操纵 CAD 自动绘图
- 提示词：**选中梁线画到CAD，标注截面尺寸**
- 实现 PKPM 与 CAD 的数据双向流转，通过指令将 PKPM 中的构件（如梁、柱）自动导出至 CAD 并完成截面尺寸标注，减少手动绘图工作量。

<img src="HelpImage/cad.gif" alt="" width="1200">






