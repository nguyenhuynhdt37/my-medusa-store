import json

lines = []
with open("/Users/huynh/.gemini/antigravity-ide/brain/cbe49369-5b60-4b46-a106-14bfef0be846/.system_generated/logs/transcript.jsonl") as f:
    for line in f:
        data = json.loads(line)
        if data.get("source") == "MODEL" and data.get("type") == "PLANNER_RESPONSE":
            tool_calls = data.get("tool_calls", [])
            for call in tool_calls:
                name = call.get("name")
                if name in ["replace_file_content", "multi_replace_file_content"]:
                    args = call.get("args", {})
                    target_file = args.get("TargetFile", "")
                    if "chat_gateway.py" in target_file:
                        lines.append(f"==== STEP {data['step_index']} ====")
                        lines.append(json.dumps(args, indent=2))
        
with open("gateway_edits.txt", "w") as f:
    f.write("\n".join(lines))
