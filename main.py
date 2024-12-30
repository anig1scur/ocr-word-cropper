import easyocr
from PIL import Image, ImageDraw, ImageFont
import os
import io
import random
from typing import Tuple, List, Dict
from collections import defaultdict
import concurrent.futures

def generate_text_image(text: str, font_size: int = 40) -> Image.Image:
    """生成文本图片作为备用"""
    try:
        font = ImageFont.truetype("msyh.ttc", font_size)
    except:
        try:
            font = ImageFont.truetype("Arial.ttf", font_size)
        except:
            font = ImageFont.load_default()
    
    dummy_draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    text_bbox = dummy_draw.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    
    padding = 10
    img_width = text_width + (padding * 2)
    img_height = text_height + (padding * 2)
    
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
    draw.text((padding, padding), text, font=font, fill=text_color)
    
    return img

def split_bbox_by_words(text, bbox):
    """将文本框按单词分割"""
    words = text.split()
    if len(words) == 1:
        return {words[0].lower(): bbox}
    
    top_left, top_right, bottom_right, bottom_left = bbox
    total_width = top_right[0] - top_left[0]
    
    word_boxes = {}
    current_pos = 0
    text_length = len(text)
    
    for word in words:
        word_start = text.find(word, current_pos)
        if word_start == -1:
            continue
        
        word_end = word_start + len(word)
        current_pos = word_end
        
        start_ratio = word_start / text_length
        end_ratio = word_end / text_length
        
        word_left = top_left[0] + total_width * start_ratio
        word_right = top_left[0] + total_width * end_ratio
        
        word_bbox = [
            [word_left, top_left[1]],
            [word_right, top_right[1]],
            [word_right, bottom_right[1]],
            [word_left, bottom_left[1]]
        ]
        
        word_boxes[word.lower()] = word_bbox
    
    return word_boxes

def process_single_image(image_path: str, target_words_set: set) -> Dict[str, List[Image.Image]]:
    """处理单张图片，返回找到的目标词及其对应的裁剪图片"""
    try:
        reader = easyocr.Reader(['en'])
        image = Image.open(image_path)
        result = reader.readtext(image)
        found_words = defaultdict(list)

        for bbox, text, prob in result:
            word_boxes = split_bbox_by_words(text, bbox)

            for word in target_words_set:
                if word in word_boxes and word not in found_words:
                    word_bbox = word_boxes[word]
                    
                    left = max(0, int(word_bbox[0][0]) - 2)
                    top = max(0, int(word_bbox[0][1]) - 2)
                    right = min(image.width, int(word_bbox[2][0]) + 2)
                    bottom = min(image.height, int(word_bbox[2][1]) + 2)
                    
                    if left < right and top < bottom:
                        cropped_image = image.crop((left, top, right, bottom))
                        found_words[word].append(cropped_image)

        return found_words
        
    except Exception as e:
        print(f"Error processing {image_path}: {str(e)}")
        return {}

def collect_words_from_images(image_dir: str, target_words: List[List[str]], max_workers: int = 4) -> Dict[str, List[Image.Image]]:
    """并行处理所有图片，收集所有找到的目标词"""
    target_words_set = {word.lower() for line in target_words for word in line}
    all_found_words = defaultdict(list)
    
    image_paths = [
        os.path.join(image_dir, f) for f in os.listdir(image_dir)
        if f.lower().endswith(('.png', '.jpg', '.jpeg'))
    ]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_path = {
            executor.submit(process_single_image, path, target_words_set): path
            for path in image_paths
        }
        
        for future in concurrent.futures.as_completed(future_to_path):
            path = future_to_path[future]
            try:
                found_words = future.result()
                for word, images in found_words.items():
                    all_found_words[word].extend(images)
            except Exception as e:
                print(f"Error processing {path}: {str(e)}")
    
    return all_found_words

def create_poem_image(found_words: Dict[str, List[Image.Image]], target_words: List[List[str]]) -> Image.Image:
    """创建最终的拼贴诗图片"""
    padding = 20
    line_spacing = 40
    background_color = 'white'
    
    # 为每个词选择一个图片（如果找到了）或生成一个
    selected_images = {}
    max_height = 0
    line_widths = []
    
    for line in target_words:
        line_width = 0
        for word in line:
            word = word.lower()
            if word in found_words and found_words[word]:
                # 随机选择一个找到的图片
                img = random.choice(found_words[word])
            else:
                # 如果没找到，生成文本图片
                img = generate_text_image(word)
            
            selected_images[word] = img
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
        
        for word in line:
            word = word.lower()
            word_image = selected_images[word]
            y_offset = (max_height - word_image.height) // 2
            result_image.paste(word_image, (current_x + x_offset, current_y + y_offset))
            current_x += word_image.width + padding
        
        current_y += max_height + line_spacing
    
    return result_image

def create_poetry_collage(image_dir: str, target_words: List[List[str]], output_path: str):
    """主函数：创建拼贴诗"""
    # 收集所有符合条件的词
    found_words = collect_words_from_images(image_dir, target_words)
    
    # 创建并保存最终图片
    poem_image = create_poem_image(found_words, target_words)
    poem_image.save(output_path)
    print(f"Saved poem image to: {output_path}")

if __name__ == "__main__":
    image_dir = "images"
    output_dir = "output"
    
    target_words = [
        ["If", "this is", "destined"],
        ["to be", "the field", "I'm", "willing"],
        ["to", "devote", "my life", "to"],
        ["why don't", "I", "start now"]
    ]
    
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "poem.png")
    
    create_poetry_collage(image_dir, target_words, output_path)
