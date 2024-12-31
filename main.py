import easyocr
from PIL import Image, ImageDraw, ImageFont
import os
import io
import random
from typing import Tuple, List, Dict
from collections import defaultdict
import concurrent.futures
import re


def split_bbox_by_phrases(text: str, bbox, target_phrases: set) -> Dict[str, List]:
    """将文本框按短语分割"""
    text = text.lower()
    phrase_boxes = defaultdict(list)
    
    # 获取边界框的坐标
    top_left, top_right, bottom_right, bottom_left = bbox
    total_width = top_right[0] - top_left[0]
    char_width = total_width / len(text)  # 估算每个字符的宽度
    
    # 查找每个目标短语
    for phrase in target_phrases:
        phrase = phrase.lower()
        start_idx = 0
        
        while True:
            # 查找短语位置
            pos = text.find(phrase, start_idx)
            if pos == -1:
                break
                
            # 计算短语的边界框
            phrase_left = top_left[0] + (pos * char_width)
            phrase_right = phrase_left + (len(phrase) * char_width)
            
            # 创建短语的边界框
            phrase_bbox = [
                [phrase_left, top_left[1]],      # top_left
                [phrase_right, top_right[1]],    # top_right
                [phrase_right, bottom_right[1]], # bottom_right
                [phrase_left, bottom_left[1]]    # bottom_left
            ]
            
            phrase_boxes[phrase].append(phrase_bbox)
            start_idx = pos + 1  # 继续查找下一个匹配
    
    return phrase_boxes

def process_single_image(image_path: str, target_phrases: set) -> Dict[str, List[Image.Image]]:
    """处理单张图片，返回找到的目标短语及其对应的裁剪图片"""
    try:
        reader = easyocr.Reader(['ch_sim', 'en'])
        image = Image.open(image_path)
        result = reader.readtext(image)
        
        found_phrases = defaultdict(list)
        
        for bbox, text, prob in result:
            # 使用新的短语分割函数
            phrase_boxes = split_bbox_by_phrases(text, bbox, target_phrases)
            
            # 处理每个找到的短语
            for phrase, boxes in phrase_boxes.items():
                for box in boxes:
                    # 获取边界框坐标
                    left = max(0, int(box[0][0]) - 5)
                    top = max(0, int(box[0][1]) - 5)
                    right = min(image.width, int(box[2][0]) + 5)
                    bottom = min(image.height, int(box[2][1]) + 5)
                    
                    # 确保边界框有效
                    if left < right and top < bottom:
                        try:
                            cropped = image.crop((left, top, right, bottom))
                            # 对裁剪结果进行额外验证
                            if cropped.size[0] > 0 and cropped.size[1] > 0:
                                found_phrases[phrase].append(cropped)
                        except Exception as e:
                            print(f"Cropping error for phrase '{phrase}': {str(e)}")
        
        return found_phrases
        
    except Exception as e:
        print(f"Error processing {image_path}: {str(e)}")
        return {}

def adjust_bbox_for_chinese(bbox, text: str) -> List:
    """调整边界框以更好地适应中文字符"""
    top_left, top_right, bottom_right, bottom_left = bbox
    
    # 检测是否包含中文字符
    has_chinese = any('\u4e00' <= char <= '\u9fff' for char in text)
    
    if has_chinese:
        # 为中文字符提供更大的空间
        width = top_right[0] - top_left[0]
        height = bottom_left[1] - top_left[1]
        char_width = width / len(text) * 1.2  # 增加20%的宽度
        
        return [
            [top_left[0], top_left[1]],
            [top_left[0] + (char_width * len(text)), top_right[1]],
            [top_left[0] + (char_width * len(text)), bottom_right[1]],
            [top_left[0], bottom_left[1]]
        ]
    
    return bbox

def create_poetry_collage(image_dir: str, target_words: List[List[str]], output_path: str):
    """主函数：创建拼贴诗"""
    # 将目标词组转换为集合，同时添加小写版本
    target_phrases = {phrase.lower() for line in target_words for phrase in line}
    
    # 收集所有匹配的短语
    found_phrases = collect_phrases_from_images(image_dir, target_words)
    
    # 检查找到的短语
    missing_phrases = target_phrases - set(found_phrases.keys())
    if missing_phrases:
        print(f"Following phrases were not found and will be generated: {missing_phrases}")
    
    # 创建并保存最终图片
    poem_image = create_poem_image(found_phrases, target_words)
    poem_image.save(output_path)
    print(f"Saved poem image to: {output_path}")

def generate_text_image(text: str, font_size: int = 40) -> Image.Image:
    """生成文本图片作为备用"""
    # 尝试加载中文字体
    try:
        # 依次尝试不同的中文字体
        font_paths = [
            "simhei.ttf",  # Windows 黑体
            "msyh.ttc",    # Windows 雅黑
            "SimHei.ttf",  # macOS 黑体
            "STHeiti Light.ttc",  # macOS 华文黑体
            "NotoSansSC-Regular.otf",  # Google Noto Sans SC
            "Arial.ttf"    # 退化方案
        ]
        font = None
        for font_path in font_paths:
            try:
                font = ImageFont.truetype(font_path, font_size)
                break
            except:
                continue
        
        if font is None:
            font = ImageFont.load_default()
    except:
        font = ImageFont.load_default()
    
    # 计算文本大小
    dummy_draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    text_bbox = dummy_draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    
    # 添加较大的padding以适应中文
    padding = 20
    img_width = text_width + (padding * 2)
    img_height = text_height + (padding * 2)
    
    # 生成柔和的背景色
    hue = random.random()
    saturation = random.uniform(0.1, 0.3)
    value = random.uniform(0.9, 1.0)
    
    def hsv_to_rgb(h: float, s: float, v: float) -> Tuple[int, int, int]:
        h_i = int(h * 6)
        f = h * 6 - h_i
        p = v * (1 - s)
        q = v * (1 - f * s)
        t = v * (1 - (1 - f) * s)
        
        if h_i == 0: r, g, b = v, t, p
        elif h_i == 1: r, g, b = q, v, p
        elif h_i == 2: r, g, b = p, v, t
        elif h_i == 3: r, g, b = p, q, v
        elif h_i == 4: r, g, b = t, p, v
        else: r, g, b = v, p, q
        
        return (int(r * 255), int(g * 255), int(b * 255))
    
    bg_color = hsv_to_rgb(hue, saturation, value)
    text_color = (50, 50, 50)
    
    img = Image.new('RGB', (img_width, img_height), bg_color)
    draw = ImageDraw.Draw(img)
    
    # 居中绘制文本
    text_x = (img_width - text_width) // 2
    text_y = (img_height - text_height) // 2
    draw.text((text_x, text_y), text, font=font, fill=text_color)
    
    return img

def find_phrase_in_text(text: str, phrase: str) -> List[Tuple[int, int]]:
    """在文本中查找短语，返回所有匹配位置"""
    phrase = phrase.lower()
    text = text.lower()
    
    # 处理特殊字符
    escaped_phrase = re.escape(phrase)
    matches = list(re.finditer(escaped_phrase, text))
    return [(m.start(), m.end()) for m in matches]

def collect_phrases_from_images(image_dir: str, target_words: List[List[str]], max_workers: int = 4) -> Dict[str, List[Image.Image]]:
    """并行处理所有图片，收集所有找到的目标短语"""
    # 将所有短语转换为小写并存入集合
    target_phrases = {phrase.lower() for line in target_words for phrase in line}
    all_found_phrases = defaultdict(list)
    
    image_paths = [
        os.path.join(image_dir, f) for f in os.listdir(image_dir)
        if f.lower().endswith(('.png', '.jpg', '.jpeg'))
    ]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_path = {
            executor.submit(process_single_image, path, target_phrases): path
            for path in image_paths
        }
        
        for future in concurrent.futures.as_completed(future_to_path):
            path = future_to_path[future]
            try:
                found_phrases = future.result()
                for phrase, images in found_phrases.items():
                    all_found_phrases[phrase].extend(images)
            except Exception as e:
                print(f"Error processing {path}: {str(e)}")
    
    return all_found_phrases

def create_poem_image(found_phrases: Dict[str, List[Image.Image]], target_words: List[List[str]]) -> Image.Image:
    """创建最终的拼贴诗图片"""
    padding = 30  # 增加间距以适应中文
    line_spacing = 50  # 增加行间距
    background_color = 'white'
    
    # 为每个短语选择或生成图片
    selected_images = {}
    max_height = 0
    line_widths = []
    
    for line in target_words:
        line_width = 0
        for phrase in line:
            phrase = phrase.lower()
            if phrase in found_phrases and found_phrases[phrase]:
                # 随机选择一个找到的图片
                img = random.choice(found_phrases[phrase])
            else:
                # 如果没找到，生成文本图片
                img = generate_text_image(phrase)
            
            selected_images[phrase] = img
            line_width += img.width + padding
            max_height = max(max_height, img.height)
        
        line_widths.append(line_width - padding)
    
    # 创建最终图片
    total_width = max(line_widths)
    total_height = (len(target_words) * max_height) + ((len(target_words) - 1) * line_spacing)
    
    result_image = Image.new('RGB', (total_width + padding * 2, total_height + padding * 2), background_color)
    
    # 绘制每一行
    current_y = padding
    for line_idx, line in enumerate(target_words):
        current_x = padding
        line_width = line_widths[line_idx]
        x_offset = (total_width - line_width) // 2
        
        for phrase in line:
            phrase = phrase.lower()
            phrase_image = selected_images[phrase]
            y_offset = (max_height - phrase_image.height) // 2
            result_image.paste(phrase_image, (current_x + x_offset, current_y + y_offset))
            current_x += phrase_image.width + padding
        
        current_y += max_height + line_spacing
    
    return result_image

if __name__ == "__main__":
    image_dir = "images"
    output_dir = "output"
    
    target_words = [
        ["白砂糖", "carries", "money"],
        ["Let's talk", "your world"],
        ["stop at", "promo code", "when you use", "保健食品"],
        ["learn how", "卤猪蹄"]
    ]
    
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "poem.png")
    
    create_poetry_collage(image_dir, target_words, output_path)
