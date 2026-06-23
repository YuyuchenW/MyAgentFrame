"""端到端示例：让大模型通过 docx 工具集自动生成一份 Word 文档。

运行前请确保 .env 中已配置 LLM_MODEL_ID / LLM_API_KEY / LLM_BASE_URL。
可选：设置 DOCX_WORKSPACE 环境变量指定文档输出根目录（默认当前工作目录）。
"""

from dotenv import load_dotenv

from my_hello_agents.core.llm import HelloAgentsLLM
from my_hello_agents.tools import get_docx_tool_schemas, run_with_tools


SYSTEM_PROMPT = """你是 Word 文档助手，能通过调用 docx_* 工具操作 Word 文档。

工作流：
1. 若目标文件不存在，先调用 docx_create 创建。
2. 用 docx_add_heading / docx_add_paragraph / docx_add_table 等填充内容。
3. 需要了解已有内容时，调用 docx_read_text / docx_list_structure。
4. 完成后向用户用一句话说明结果。

注意：
- 所有 file_path 都是相对 workspace 的路径，例如 text.docx。
- 一次性文件制：每个工具内部都会重新打开并保存文件。
- 工具结果中 truncated=true 表示已截断，请改用 docx_list_structure。
"""

relay_table_tsv = r"""RULES	1_CN_继电器产品型号	1_EN_继电器产品型号	2_CN_线圈电源类型/线圈电压类型	2_EN_线圈电源类型/线圈电压类型	3_CN_线圈规格号/线圈工作电压	3_EN_线圈规格号/线圈工作电压	4_CN_触点形式	4_EN_触点形式	5_CN_触点数	5_EN_触点数	6_CN_引出端形式/负载引出端方式	6_EN_引出端形式/负载引出端方式	7_CN_安装形式/安装脚位	7_EN_安装形式/安装脚位	8_CN_封装形式	8_EN_封装形式	9_CN_引出端结构形式/引出端	9_EN_引出端结构形式/引出端	10_CN_线圈功率/线圈功耗	10_EN_线圈功率/线圈功耗	11_CN_线圈特征/线圈类型/工作方式+线圈特征	11_EN_线圈特征/线圈类型/工作方式+线圈特征	12_CN_触点材料	12_EN_触点材料	13_CN_绝缘等级/线圈绝缘等级	13_EN_绝缘等级/线圈绝缘等级	14_CN_线圈并联元件/组合元件代号	14_EN_线圈并联元件/组合元件代号	15_CN_面板结构形式代号	15_EN_面板结构形式代号	16_CN_触点镀层代号/镀层代号/触点镀层	16_EN_触点镀层代号/镀层代号/触点镀层	17_CN_其他特殊要求代号	17_EN_其他特殊要求代号	18_CN_极性代号/极性特点/极性	18_EN_极性代号/极性特点/极性	19_CN_包装形式	19_EN_包装形式	20_CN_负载电压（单位：V）	20_EN_负载电压（单位：V）	21_CN_辅助触点形式	21_EN_辅助触点形式	22_CN_线圈引出端方式/线圈引出脚位	22_EN_线圈引出端方式/线圈引出脚位	23_CN_外壳结构	23_EN_外壳结构	24_CN_底座结构	24_EN_底座结构	25_CN_产品特性号	25_EN_产品特性号	26_CN_额定线圈功率（功耗）（数值）（单位：W）	26_EN_额定线圈功率（功耗）（数值）（单位：W）	27_CN_介质耐压（线圈与触点间）（单位：V）	27_EN_介质耐压（线圈与触点间）（单位：V）	28_CN_动作时间（单位：ms）	28_EN_动作时间（单位：ms）	29_CN_释放时间（单位：ms）	29_EN_释放时间（单位：ms）	30_CN_线圈电阻（单位：Ω）	30_EN_线圈电阻（单位：Ω）	31_CN_爬电距离（单位：mm）	31_EN_爬电距离（单位：mm）	32_CN_电气距离（单位：mm）	32_EN_电气距离（单位：mm）	33_CN_绝缘电阻（单位：MΩ）	33_EN_绝缘电阻（单位：MΩ）	34_CN_最大额定切换电流（触点负载（额定））（AC）（单位：A）	34_EN_最大额定切换电流（触点负载（额定））（AC）（单位：A）	35_CN_最大额定切换电流（触点负载（额定））（DC）（单位：A）	35_EN_最大额定切换电流（触点负载（额定））（DC）（单位：A）	36_CN_最大切换电压（AC）（单位：V）	36_EN_最大切换电压（AC）（单位：V）	37_CN_最大切换电压（DC）（单位：V）	37_EN_最大切换电压（DC）（单位：V）	38_CN_温度范围（最低）（单位：℃）	38_EN_温度范围（最低）（单位：℃）	39_CN_温度范围（最高）（单位：℃）	39_EN_温度范围（最高）（单位：℃）	40_CN_长（单位：mm）	40_EN_长（单位：mm）	41_CN_宽（单位：mm）	41_EN_宽（单位：mm）	42_CN_高（单位：mm）	42_EN_高（单位：mm）	43_CN_机械耐久性（单位：次）	43_EN_机械耐久性（单位：次）	44_CN_电耐久性（单位：次）	44_EN_电耐久性（单位：次）	45_CN_IEC60335-1认证	45_EN_IEC60335-1认证	46_CN_手动作业	46_EN_手动作业	47_CN_指示器（机械，LED）	47_EN_指示器（机械，LED）	48_CN_防爆认证	48_EN_防爆认证	49_CN_触点间隙	49_EN_触点间隙	50_CN_物料组（SAP物料组）	50_EN_物料组（SAP物料组）	51_CN_产品类型	51_EN_产品类型	52_CN_产品描述	52_EN_产品描述	53_CN_产品应用领域	53_EN_产品应用领域	54_CN_产品应用场合	54_EN_产品应用场合	55_CN_生产工厂	55_EN_生产工厂	56_CN_重量（g）	56_EN_重量（g）	57_CN_体积	57_EN_体积	58_CN_产品认证	58_EN_产品认证	59_CN_产品认证号	59_EN_产品认证号	60_CN_竞争对手	60_EN_竞争对手	61_CN_对手产品型号	61_EN_对手产品型号
HF190F 2H/48-2HTF	HF190F 2H	HF190F 2H	DC	DC	48	48	二组常开	2 From A	单触点	Single contact	印制板式	PCB	-	-	-	-	-	-	-	-	单稳态	Single side stable	AgSnO<sub>2</sub>	AgSnO<sub>2</sub>	F级	Class F	-	-	-	-	-	-	-	-	-	-	吸塑片	plastics packing	277	277	-	-	-	-	-	-	-	-	-	-	约1.4W	Approx. 1.4W	4000VAC 1min	4000VAC 1min	15	15	10	10	12:102×（1±10%）#18:231×（1±10%）#24:411×（1±10%）#48:1645×（1±10%）	12:102×（1±10%）#18:231×（1±10%）#24:411×（1±10%）#48:1645×（1±10%）	9.6	9.6	7.5	7.5	1000	1000	20	0	-	-	460	460	-	-	-40	-40	105	105	35	35	16	16	28	28	1000000	1000000	30000	30000	-	-	-	-	-	-	-	-	≥2.1	≥2.1	CPACB8287	CPACB8287	功率继电器	Power Relay	小型大功率继电器	MIiniature High Power Relay	随车充，充电桩等	Car charger, charging pile, etc	-	-	厦门宏发电声股份有限公司	Xiamen Hongfa Electroacoustic Co.,Ltd	约30	Approx. 30	35×16×28	35×16×28	UL/CUL  TUV	UL/CUL  TUV	E 133481  R 50509389	E 133481  R 50509389	-	-	-	-
HF190F 2H/12-2HTF	HF190F 2H	HF190F 2H	DC	DC	12	12	二组常开	2 From A	单触点	Single contact	印制板式	PCB	-	-	-	-	-	-	-	-	单稳态	Single side stable	AgSnO<sub>2</sub>	AgSnO<sub>2</sub>	F级	Class F	-	-	-	-	-	-	-	-	-	-	吸塑片	plastics packing	277	277	-	-	-	-	-	-	-	-	-	-	约1.4W	Approx. 1.4W	4000VAC 1min	4000VAC 1min	15	15	10	10	12:102×（1±10%）#18:231×（1±10%）#24:411×（1±10%）#48:1645×（1±10%）	12:102×（1±10%）#18:231×（1±10%）#24:411×（1±10%）#48:1645×（1±10%）	9.6	9.6	7.5	7.5	1000	1000	20	0	-	-	460	460	-	-	-40	-40	105	105	35	35	16	16	28	28	1000000	1000000	30000	30000	-	-	-	-	-	-	-	-	≥2.1	≥2.1	CPACB8287	CPACB8287	功率继电器	Power Relay	小型大功率继电器	MIiniature High Power Relay	随车充，充电桩等	Car charger, charging pile, etc	-	-	厦门宏发电声股份有限公司	Xiamen Hongfa Electroacoustic Co.,Ltd	约30	Approx. 30	35×16×28	35×16×28	UL/CUL  TUV	UL/CUL  TUV	E 133481  R 50509389	E 133481  R 50509389	-	-	-	-
HF190F 2H/24-2HTF	HF190F 2H	HF190F 2H	DC	DC	24	24	二组常开	2 From A	单触点	Single contact	印制板式	PCB	-	-	-	-	-	-	-	-	单稳态	Single side stable	AgSnO<sub>2</sub>	AgSnO<sub>2</sub>	F级	Class F	-	-	-	-	-	-	-	-	-	-	吸塑片	plastics packing	277	277	-	-	-	-	-	-	-	-	-	-	约1.4W	Approx. 1.4W	4000VAC 1min	4000VAC 1min	15	15	10	10	12:102×（1±10%）#18:231×（1±10%）#24:411×（1±10%）#48:1645×（1±10%）	12:102×（1±10%）#18:231×（1±10%）#24:411×（1±10%）#48:1645×（1±10%）	9.6	9.6	7.5	7.5	1000	1000	20	0	-	-	460	460	-	-	-40	-40	105	105	35	35	16	16	28	28	1000000	1000000	30000	30000	-	-	-	-	-	-	-	-	≥2.1	≥2.1	CPACB8287	CPACB8287	功率继电器	Power Relay	小型大功率继电器	MIiniature High Power Relay	随车充，充电桩等	Car charger, charging pile, etc	-	-	厦门宏发电声股份有限公司	Xiamen Hongfa Electroacoustic Co.,Ltd	约30	Approx. 30	35×16×28	35×16×28	UL/CUL  TUV	UL/CUL  TUV	E 133481  R 50509389	E 133481  R 50509389	-	-	-	-
HF190F 2H/18-2HTF	HF190F 2H	HF190F 2H	DC	DC	18	18	二组常开	2 From A	单触点	Single contact	印制板式	PCB	-	-	-	-	-	-	-	-	单稳态	Single side stable	AgSnO<sub>2</sub>	AgSnO<sub>2</sub>	F级	Class F	-	-	-	-	-	-	-	-	-	-	吸塑片	plastics packing	277	277	-	-	-	-	-	-	-	-	-	-	约1.4W	Approx. 1.4W	4000VAC 1min	4000VAC 1min	15	15	10	10	12:102×（1±10%）#18:231×（1±10%）#24:411×（1±10%）#48:1645×（1±10%）	12:102×（1±10%）#18:231×（1±10%）#24:411×（1±10%）#48:1645×（1±10%）	9.6	9.6	7.5	7.5	1000	1000	20	0	-	-	460	460	-	-	-40	-40	105	105	35	35	16	16	28	28	1000000	1000000	30000	30000	-	-	-	-	-	-	-	-	≥2.1	≥2.1	CPACB8287	CPACB8287	功率继电器	Power Relay	小型大功率继电器	MIiniature High Power Relay	随车充，充电桩等	Car charger, charging pile, etc	-	-	厦门宏发电声股份有限公司	Xiamen Hongfa Electroacoustic Co.,Ltd	约30	Approx. 30	35×16×28	35×16×28	UL/CUL  TUV	UL/CUL  TUV	E 133481  R 50509389	E 133481  R 50509389	-	-	-	-"""

def main():
    load_dotenv()
    llm = HelloAgentsLLM()
    tools = get_docx_tool_schemas()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"《text.docx》是一份产品说明书文档，其中红色字体是需要替代的内容，蓝色字体是说明，"
                f"根据以下表格数据替换原始文档中的信息并且保持原有的字体形式，对于表格多余的表格行要删除，表格行不足要添加 {relay_table_tsv}"
            ),
        },
    ]

    print(f"已加载 {len(tools)} 个 docx 工具")
    final = run_with_tools(llm, messages, tools, max_steps=150, verbose=True)
    print("\n===== 最终结果 =====")
    print(final)


if __name__ == "__main__":
    main()