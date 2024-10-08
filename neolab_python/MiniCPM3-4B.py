from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import time

start_time = time.time()
# 指定本地模型路径
local_model_path = "C:\\Users\\Administrator\\.cache\\huggingface\\openbmb\\MiniCPM3-4B"
device = "cpu"
# 加载 tokenizer 和模型
tokenizer = AutoTokenizer.from_pretrained(local_model_path, trust_remote_code=True)
# 设置 pad_token_id
tokenizer.pad_token_id = tokenizer.eos_token_id if tokenizer.eos_token_id is not None else 0
model = AutoModelForCausalLM.from_pretrained(local_model_path, torch_dtype=torch.bfloat16, device_map=device, trust_remote_code=True)
# 构建输入消息
messages = [
    {"role": "user", "content": "什么是核电站？"},
]
# 设置attention_mask
model_inputs = tokenizer.apply_chat_template(messages, return_tensors="pt", add_generation_prompt=True, padding=True, truncation=True)
# 应用聊天模板并转换为张量
model_inputs = tokenizer.apply_chat_template(messages, return_tensors="pt", add_generation_prompt=True).to(device)
# 生成模型输出
model_outputs = model.generate(
    model_inputs,
    max_new_tokens=50,
    top_p=0.7,
    temperature=0.7
)
# 提取生成的 token ids
output_token_ids = [
    model_outputs[i][len(model_inputs[i]):] for i in range(len(model_inputs))
]
# 解码生成的 token ids
responses = tokenizer.batch_decode(output_token_ids, skip_special_tokens=True)[0]
print(responses)
end_time = time.time()
elapsed_time = end_time - start_time
print(f"程序运行时间: {elapsed_time:.2f} 秒")