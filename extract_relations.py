import spacy
import pandas as pd
import re
from pathlib import Path

# 加载英文模型
nlp = spacy.load("en_core_web_sm")

# 预定义关系模板（基于依存路径和词性）
RELATION_PATTERNS = [
    # 出生地: 实体 + "was born in" + 地点
    {"trigger": "born", "dep": "prep", "rel": "bornIn", "obj_ent_type": "GPE"},
    # 提出: 实体 + "proposed" + 概念
    {"trigger": "proposed", "dep": "dobj", "rel": "proposed", "obj_ent_type": ""},
    # 参与: 实体 + "worked at" + 机构/地点
    {"trigger": "worked", "dep": "prep", "rel": "participatedIn", "obj_ent_type": "ORG"},
    # 写作: 实体 + "wrote" + 作品
    {"trigger": "wrote", "dep": "dobj", "rel": "wrote", "obj_ent_type": ""},
    # 获奖: 实体 + "was appointed" + 奖项
    {"trigger": "appointed", "dep": "pobj", "rel": "awarded", "obj_ent_type": ""},
    # 逝世: 实体 + "died in" + 地点
    {"trigger": "died", "dep": "prep", "rel": "diedIn", "obj_ent_type": "GPE"},
]

def extract_triples(text):
    doc = nlp(text)
    triples = []
    # 预先保存所有实体和对应的span
    entities = [(ent.text, ent.label_) for ent in doc.ents]
    
    for sent in doc.sents:
        # 对于每个句子，寻找主谓结构
        for token in sent:
            # 检查是否是触发词（动词）
            if token.pos_ == "VERB" and token.lemma_ in [p["trigger"] for p in RELATION_PATTERNS]:
                pattern = next((p for p in RELATION_PATTERNS if p["trigger"] == token.lemma_), None)
                if not pattern:
                    continue
                # 寻找主语（头实体）
                subj = None
                for child in token.children:
                    if child.dep_ == "nsubj" or child.dep_ == "nsubjpass":
                        subj = child.text
                        break
                # 寻找宾语（尾实体）
                obj = None
                if pattern["dep"] == "dobj":
                    for child in token.children:
                        if child.dep_ == "dobj":
                            obj = child.text
                            break
                elif pattern["dep"] == "prep":
                    for child in token.children:
                        if child.dep_ == "prep":
                            # 获取介词之后的宾语
                            for grandchild in child.children:
                                if grandchild.dep_ == "pobj":
                                    obj = grandchild.text
                                    break
                elif pattern["dep"] == "pobj":
                    # 直接作为介词宾语（如 appointed Officer...）
                    for child in token.children:
                        if child.dep_ == "pobj":
                            obj = child.text
                            break
                
                if subj and obj:
                    # 可选的实体类型约束
                    if pattern["obj_ent_type"]:
                        # 检查obj是否被识别为指定类型
                        obj_span = None
                        for ent_text, ent_type in entities:
                            if obj in ent_text:
                                if ent_type == pattern["obj_ent_type"]:
                                    obj_span = ent_text
                                    break
                        if not obj_span:
                            continue
                        else:
                            obj = obj_span
                    triples.append((subj, pattern["rel"], obj))
    return triples

def main():
    # 读取文本
    text_path = Path("turing_text.txt")
    if not text_path.exists():
        print("请创建 turing_text.txt 文件并放入关于图灵的英文文本")
        return
    text = text_path.read_text(encoding="utf-8")
    
    # 抽取三元组
    triples = extract_triples(text)
    
    # 输出到控制台和CSV
    df = pd.DataFrame(triples, columns=["subject", "predicate", "object"])
    print("抽取到的三元组：")
    print(df)
    
    # 保存为CSV，并与原有知识图谱合并（去重）
    output_csv = Path("extracted_triples.csv")
    df.to_csv(output_csv, index=False)
    print(f"\n三元组已保存至 {output_csv}")
    
    # 可选：与原有 triples.csv 合并
    original_csv = Path("triples.csv")
    if original_csv.exists():
        original_df = pd.read_csv(original_csv)
        combined_df = pd.concat([original_df, df]).drop_duplicates()
        combined_df.to_csv(original_csv, index=False)
        print(f"已将新三元组合并到 {original_csv}，去重后总数为 {len(combined_df)}")
    else:
        print("未找到原有 triples.csv，仅生成了新文件")

if __name__ == "__main__":
    main()
