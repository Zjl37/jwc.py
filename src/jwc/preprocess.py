import re

T_LESSON_RULES = [
    (r"物理实验", "🔬"),
    (r"电.+实验", "⚡"),

    (r"思想道德与法治", "🟢"),
    (r"形势与政策", "🔴"),
    (r"习.+概", "🔴"),
    (r"近现代史", "🟠"),
    (r"马.+原", "🟡"),
    (r"国家安全教育", "♦️"),
    (r"英语", "🔤"),
    (r"心理健康", "💟"),
    (r"导论", "🧑‍🏫"),
    (r"高级语言程序设计", "©️"),
    (r"物理", "🟦"),
    (r"复变", "🟨"),
    (r"最优化", "⬜️"),
    (r"数字逻辑", "🟧"),
    (r"离散", "🟥"),
    (r"概率论", "🟦"),
    (r"微积分", "🟩"),
    (r"代数与几何", "🟪"),
    (r"电路与电子学", "🟫"),
    (r"计算思维与信息基础", "🧑‍💻"),
    (r"田径", "🏃"),
    (r"排球", "🏐"),
    (r"篮球", "🏀"),
    (r"网球", "🎾"),
    (r"足球", "⚽"),
    (r"游泳", "🏊‍"),
    (r"街舞", "👯"),
    (r"体育[\s\S]+基", "‍🦵"),

    (r"天文", "🔭"),
    (r"行星", "🪐"),
    (r"深空", "🌌"),
    (r"^数字化素养", "🌸"),
    (r"宝玉石", "💎"),
    (r"德语", "🇩🇪"),
    (r"插花", "🌷"),
    (r"急救", "🆘"),
    (r"^爱情", "💞"),
    (r"书法", "✒️"),
    (r"演讲", "🎤"),
    (r"文字肖像", "👤"),
    (r"敦煌", "🌅"),
    (r"网络安全", "🔐"),
    (r"朗诵", "🎤"),
    (r"声乐", "🎵"),
    (r"音乐", "🎶"),
    (r"考古", "📜"),
    (r"服饰", "👕"),
    (r"电影", "🎞"),
    (r"汉语", "🀄"),
    (r"批判性思维", "🧐"),
    (r"^(性科学|婚恋)", "💚"),
    (r"道家", "☯️"),
    (r"人际关系", "🧑‍🤝‍🧑"),
    (r"情绪", "💙"),
    (r"犯罪", "😈"),
    (r"西方政治", "🗽"),
    (r"能源", "🔋"),
    (r"全球", "🌏"),
    (r"供水", "🚰"),
    (r"游戏", "🎲"),
    (r"宇宙", "🪐"),
    (r"实验室", "🥽"),
    (r"数据", "📊"),
    (r"显微", "🔬"),
    (r"[色光]谱", "🌈"),
    (r"火箭", "🚀"),
    (r"三维", "📦"),
    (r"聚焦", "🔦"),
    (r"性别", "⚧"),
    (r"生命", "☘"),
    (r"心理", "💟"),
    (r"文学", "📄"),
    (r"创意", "💡"),
    (r"艺术", "🎨"),
    (r"光", "🔦"),
    (r"画", "🎨"),
    (r"海", "🌊"),
]
T_LESSON_RULES = list(map(lambda r: (re.compile(r[0], flags=re.M), r[1]), T_LESSON_RULES))
def transform_lesson_name(name: str) -> str:
    for pattern, prefix in T_LESSON_RULES:
        if re.search(pattern, name):
            return prefix + name
    print(f"[i] Lesson name {name} is not transformed.")
    return name

T_LAB_RULES = [
    (r"逻辑", "▶️"),
    (r"物理实验", "🔬"),
    (r"电.+实验", "⚡"),
    (r"高级语言程序设计", "🖥"),

    (r"大模型", "💬"),
]
T_LAB_RULES = list(map(lambda r: (re.compile(r[0], flags=re.M), r[1]), T_LAB_RULES))
def transform_lab_name(name: str, lab_name: str) -> str:
    for pattern, prefix in T_LAB_RULES:
        if re.search(pattern, name):
            return prefix + (lab_name or name)
    print(f"[i] Lab name {name} is not transformed.")
    return name


T_LOCATION_RULES = [
    (r"^(A.+)", "\\1\n哈尔滨工业大学深圳校区A栋 平山一路6号"),
    (r"^(F.+)", "\\1\n哈尔滨工业大学深圳校区F栋\n平山一路"),
    (r"^(G.+)", "\\1\n中国广东省深圳市南山区哈尔滨工业大学深圳校区G栋"),
    (r"^(H.+)", "\\1\n哈尔滨工业大学深圳校区H栋 平山一路"),
    (r"^(J.+)", "\\1\n哈尔滨工业大学(深圳)师生活动中心\n平山一路哈尔滨工业大学深圳校区"),
    (r"^(K.+)", "\\1\n哈尔滨工业大学深圳校区K座 平山一路"),
    (r"^(T2.+)", "\\1\n哈尔滨工业大学深圳校区T2栋 平山一路"),
    (r"^(T3.+)", "\\1\n哈尔滨工业大学深圳校区T3栋 平山一路"),
    (r"^(T4.+)", "\\1\n中国广东省深圳市南山区哈尔滨工业大学深圳校区T4栋"),
    (r"^(T5.+)", "\\1\n哈尔滨工业大学深圳校区T5栋 平山一路"),
    (r"哈工大田径场", "哈尔滨工业大学深圳校区运动场"),
]
T_LOCATION_RULES = list(map(lambda r: (re.compile(r[0], flags=re.M), r[1]), T_LOCATION_RULES))
def location_detail(text: str) -> str:
    for pattern, repl in T_LOCATION_RULES:
        res = re.sub(pattern, repl, text)
        if res != text:
            return res
    print(f"[i] Location {text} is not transformed.")
    return text
