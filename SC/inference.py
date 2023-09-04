import argparse
import json
import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline, GPTNeoXTokenizerFast
import datetime
from src.utils import Prompter, get_logger
import warnings
from tqdm import tqdm

# 경고 메시지를 무시
warnings.filterwarnings("ignore", category=UserWarning)


parser = argparse.ArgumentParser(prog="inference", description="Inference with Kullm")
parser.add_argument("--model-ckpt-path", type=str, default="/home/dmz/project/Korean_2023/SC/outputs/model",help="Kullm model path")

def inference(args):
    logger = get_logger("inference")

    MODEL = args.model_ckpt_path
    logger.info(f'[+] Load Model from "{MODEL}"')

    model = AutoModelForCausalLM.from_pretrained(
        MODEL,
        torch_dtype=torch.float32,
        low_cpu_mem_usage=True,
    ).to(device=f"cuda", non_blocking=True)
    model.eval()
    pipe = pipeline("text-generation", model=model, tokenizer=MODEL, device=0)

    prompter = Prompter("kullm")

    logger.info("[+] Load Dataset")
    data_path = "resource/data/nikluge-sc-2023-test.jsonl"
    test_data = load_dataset("json", data_files=data_path)
    test_data = test_data["train"]
    

    logger.info("[+] Start Inference")
    
    def infer(instruction="", input_text=""):
        prompt = prompter.generate_prompt(instruction, input_text)
        output = pipe(prompt, max_length=512, temperature=0.2, num_beams=5, eos_token_id=2)
        s = output[0]["generated_text"]
        result = prompter.get_response(s)

        return result

    current_time = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    result_file_name = f"inference_results_{current_time}.jsonl"
    special_token_id = 3  # <|sep|> 토큰
    tokenizer = GPTNeoXTokenizerFast.from_pretrained(MODEL)
    special_token = tokenizer.decode([special_token_id])

    batch_size = 500  # 500개의 결과마다 파일에 저장
    all_output_data_points = []  # 결과를 저장할 리스트

    for i, data_point in enumerate(tqdm(test_data, desc="Processing")):  # tqdm을 사용하여 진행 상태를 표시
        instruction = "문맥에 맞는 자연스러운 한 문장이 되도록 두 문장 사이에 들어갈 한 문장을 만들어주세요."
        input_text = f"{data_point['input']['sentence1']} {special_token} {data_point['input']['sentence3']}"

        result = infer(instruction=instruction, input_text=input_text)

        output_data_point = {
            "id": data_point["id"],
            "input": data_point["input"],
            "output": result
        }

        all_output_data_points.append(output_data_point)  # 메모리에 결과 저장

        # 500개마다 파일에 저장
        if (i + 1) % batch_size == 0:
            with open(f"{result_file_name}_{i // batch_size + 1}.jsonl", "w") as f:
                for output_data_point in all_output_data_points:
                    f.write(json.dumps(output_data_point, ensure_ascii=False) + "\n")
            all_output_data_points = []  # 리스트 초기화

    # 남은 데이터 저장
    if all_output_data_points:
        with open(f"{result_file_name}_{(i // batch_size) + 1}.jsonl", "w") as f:
            for output_data_point in all_output_data_points:
                f.write(json.dumps(output_data_point, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    args = parser.parse_args()
    inference(args)