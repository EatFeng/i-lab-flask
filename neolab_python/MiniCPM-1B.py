from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import time

start_time = time.time()

torch.manual_seed(0)

# path = 'openbmb/MiniCPM-2B-sft-bf16'
local_model_path = "F:\\PythonProjects\\MiniCPM-1B"
device = 'cpu'
tokenizer = AutoTokenizer.from_pretrained(local_model_path)
model = AutoModelForCausalLM.from_pretrained(local_model_path, torch_dtype=torch.bfloat16, device_map=device, trust_remote_code=True)

print("开始推理...")
responds, history = model.chat(tokenizer,
                               "请用一句话回答：中国广核集团是什么企业？",
                               temperature=0.3,
                               top_p=0.8,
                               max_new_tokens=64)
print(responds)
end_time = time.time()
elapsed_time = end_time - start_time
print(f"程序运行时间: {elapsed_time:.2f} 秒")
