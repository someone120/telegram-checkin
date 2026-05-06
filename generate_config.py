import json

def get_input(prompt, default=None):
    """辅助函数，用于获取用户输入并处理默认值"""
    if default is not None:
        prompt_text = f"{prompt} [{default}]: "
    else:
        prompt_text = f"{prompt}: "
    
    val = input(prompt_text).strip()
    if not val and default is not None:
        return default
    return val

def main():
    print("=========================================")
    print("       TARGETS_CONFIG 交互式生成器       ")
    print("=========================================")
    print("此工具将帮助您生成多目标的 JSON 配置文件。")
    print("请按照提示输入信息，完成后将输出最终的 JSON。")
    print("将其复制到环境变量或 GitHub Actions Secrets 即可。\n")
    
    targets = []
    
    while True:
        print(f"\n--- 正在添加第 {len(targets) + 1} 个目标 ---")
        
        # 1. Target
        target = get_input("🎯 目标 (必填, 群组ID如-100... / 用户名如@bot)")
        while not target:
            print("❌ 目标 (target) 不能为空，请重新输入！")
            target = get_input("🎯 目标")
            
        # 2. Message
        message = get_input("💬 发送的消息 (message)", "/checkin")
        
        # 3. Interval
        print("\n⏳ 提示: 签到频率 (例如 1 表示每天，3 表示每 3 天)")
        interval_str = get_input("⏰ 间隔天数 (interval_days)", "1")
        try:
            interval_days = int(interval_str)
        except ValueError:
            print("⚠️ 输入无效，默认为 1 天")
            interval_days = 1
        
        # 4. Topic ID
        topic_id_str = get_input("🧵 话题 ID (topic_id, 发送到特定话题时填写, 否则留空)", "")
        
        # 组装数据
        target_dict = {
            "target": target,
            "message": message,
            "interval_days": interval_days,
        }
        
        if topic_id_str:
            try:
                target_dict["topic_id"] = int(topic_id_str)
            except ValueError:
                print("⚠️ 话题 ID 必须是数字，已忽略。")
                
        targets.append(target_dict)
        
        # 询问是否继续
        cont = get_input("\n❓ 是否继续添加其他目标? (y/N)", "N")
        if cont.lower() != 'y':
            break
            
    print("\n=========================================")
    print("✅ 配置生成完毕！")
    print("=========================================")
    
    print("\n【紧凑格式 (单行)】- 推荐用于环境变量 / GitHub Secrets:")
    compact_json = json.dumps(targets, ensure_ascii=False, separators=(',', ':'))
    print(f"\n{compact_json}\n")
    
    print("-" * 40)
    print("\n【易读格式 (多行)】- 方便您检查配置是否正确:")
    pretty_json = json.dumps(targets, ensure_ascii=False, indent=2)
    print(f"\n{pretty_json}\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n已取消操作。")
