import os
import json
import re
from PIL import Image
from PIL.PngImagePlugin import PngInfo
import numpy as np

# Tenta importar o piexif, necessário para metadados JPEG
try:
    import piexif
    piexif_available = True
except ImportError:
    piexif_available = False

class CustomImageSaver:
    version = '1.1.0'
    
    def __init__(self):
        pass
    
    @classmethod
    def INPUT_TYPES(cls):
        # Define os formatos disponíveis
        available_formats = ["png", "webp"] # WebP é suportado por padrão no Pillow moderno
        if piexif_available:
            available_formats.append("jpeg")
        
        return {
            "required": {
                "image": ("IMAGE",),
                "source": ("STRING", {"default": "", "multiline": False}),
                "title": ("STRING", {"default": "", "multiline": False}),
                "tagsfor34": ("STRING", {"default": "", "multiline": True}),
                "pixiv_tag": ("STRING", {"default": "", "multiline": False}),
                "pixiv_title": ("STRING", {"default": "", "multiline": True}),
                "pixiv_description": ("STRING", {"default": "", "multiline": True}),
                "output_path": ("STRING", {"default": "", "multiline": False}),
                "prefix": ("STRING", {"default": "image"}),
                "format": (available_formats,),
                "quality": ("INT", {"default": 95, "min": 1, "max": 100}),
                "number_padding": ("INT", {"default": 5, "min": 0, "max": 10}),
                "overwrite_existing": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                "character": ("STRING", {"default": "", "multiline": True}),
            }
        }
    
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "save_image_with_metadata"
    CATEGORY = "Custom/Image"
    OUTPUT_NODE = True
    
    def _create_directory(self, folder):
        """Cria o diretório se não existir"""
        if not os.path.exists(folder):
            try:
                os.makedirs(folder)
                print(f"Diretório {folder} criado com sucesso")
            except OSError as e:
                print(f"Erro ao criar diretório {folder}: {e}")
                raise
    
    def _process_tags(self, tags):
        """Processa as tags removendo vírgulas e corrigindo formatação"""
        if not tags:
            return ""
        
        # Remove vírgulas e espaços extras
        processed_tags = re.sub(r',\s*', ' ', tags.strip())
        
        # Corrige formatação de tags com parênteses escapados
        # Converte makima_\(chainsaw_man\) para makima_(chainsaw_man)
        processed_tags = re.sub(r'\\([()])', r'\1', processed_tags)
        
        # Remove espaços múltiplos
        processed_tags = re.sub(r'\s+', ' ', processed_tags).strip()
        
        return processed_tags
    
    def _get_next_filename(self, output_path, prefix, number_padding, ext):
        """Gera o próximo nome de arquivo disponível"""
        if number_padding == 0:
            # Para evitar sobrescrever, verifica se o arquivo base já existe
            base_path = os.path.join(output_path, f"{prefix}.{ext}")
            if not os.path.exists(base_path):
                return f"{prefix}.{ext}"
            # Se existe, inicia o contador
            counter = 1
        else:
            counter = 1

        if os.path.exists(output_path):
            existing_files = os.listdir(output_path)
            pattern = rf"^{re.escape(prefix)}_(\d+)\.{re.escape(ext)}$"
            numbers = []
            for filename in existing_files:
                match = re.match(pattern, filename)
                if match:
                    numbers.append(int(match.group(1)))
            
            if numbers:
                counter = max(numbers) + 1
        
        if number_padding == 0:
             return f"{prefix}_{counter}.{ext}"

        return f"{prefix}_{counter:0{number_padding}d}.{ext}"

    def save_image_with_metadata(self, image, source, title, tagsfor34, pixiv_tag, pixiv_title, pixiv_description, output_path, prefix, format, quality, number_padding, overwrite_existing, character=""):
        if not output_path:
            raise ValueError("O caminho de saída (output_path) deve ser fornecido")
        
        self._create_directory(output_path)
        processed_tags = self._process_tags(tagsfor34)
        
        metadata_dict = {
            "Source": source,
            "title": title,
            "tagsfor34": processed_tags,
            "pixiv_tag": pixiv_tag,
            "pixiv_title": pixiv_title,
            "pixiv_description": pixiv_description,
            "Generator": f"ARRAKIS Project - HanmaBuu v{self.version}"
        }

        # Adiciona o personagem ao dicionário apenas se for uma string válida e não vazia
        # Isso evita que valores inesperados como [False, True] sejam salvos.
        if character and isinstance(character, str) and character.strip():
            metadata_dict["character"] = character.strip()
        else:
            metadata_dict["character"] = "" # Garante que a chave sempre exista
        
        results = []
        
        for i, img_tensor in enumerate(image):
            img_array = np.clip(255.0 * img_tensor.cpu().numpy(), 0, 255).astype(np.uint8)
            img = Image.fromarray(img_array)
            
            ext = format.lower()
            
            if len(image) > 1:
                current_prefix = f"{prefix}_{i+1:0{number_padding}d}" if number_padding > 0 else f"{prefix}_{i+1}"
                filename = f"{current_prefix}.{ext}"
            else:
                filename = self._get_next_filename(output_path, prefix, number_padding, ext)
            
            file_path = os.path.join(output_path, filename)
            
            if not overwrite_existing and os.path.exists(file_path):
                print(f"Arquivo {file_path} já existe. Pulando...")
                continue

            save_params = {}
            if ext == 'png':
                pnginfo = PngInfo()
                # Adiciona metadados como tEXt para compatibilidade
                pnginfo.add_text("Source", source)
                pnginfo.add_text("title", title)
                pnginfo.add_text("tagsfor34", processed_tags)
                # Adiciona um JSON completo no campo Comment para facilitar a leitura
                pnginfo.add_text("Comment", json.dumps(metadata_dict, ensure_ascii=False))
                
                save_params['pnginfo'] = pnginfo
                # Mapeia qualidade (1-100) para compress_level (0-9)
                # Qualidade mais alta = menor compressão
                compress_level = max(0, min(9, 9 - int((quality - 1) / 11)))
                save_params['compress_level'] = compress_level
                save_params['optimize'] = False

            elif ext == 'jpeg' or ext == 'webp':
                if not piexif_available:
                    print(f"AVISO: Biblioteca 'piexif' não encontrada. Metadados não serão salvos no {ext.upper()}.")
                else:
                    # Converte para RGB se necessário, pois JPEG não suporta RGBA
                    if img.mode == 'RGBA':
                        img = img.convert('RGB')
                    
                    # Converte o dicionário de metadados para uma string JSON
                    metadata_json_string = json.dumps(metadata_dict, ensure_ascii=False)
                    
                    # Salva o JSON no campo ImageDescription (mais simples e compatível)
                    # O campo é codificado em bytes usando UTF-8
                    exif_dict = {"0th": {piexif.ImageIFD.ImageDescription: metadata_json_string.encode('utf-8')}}
                    exif_bytes = piexif.dump(exif_dict)
                    save_params['exif'] = exif_bytes
                
                save_params['quality'] = quality
                if ext == 'jpeg':
                    save_params['subsampling'] = 0 # Mantém a qualidade da cor
                    save_params['optimize'] = True
                elif ext == 'webp':
                    # WebP pode ser lossless com quality 100
                    save_params['lossless'] = quality == 100
                    save_params['method'] = 6 # method 6 é o mais lento e melhor

            try:
                img.save(file_path, format.upper(), **save_params)
                print(f"Imagem salva com sucesso: {file_path}")
                
                results.append({
                    "filename": filename,
                    "subfolder": "",
                    "type": "output"
                })
                
            except Exception as e:
                print(f"Erro ao salvar imagem {file_path}: {e}")
                raise
        
        return {
            "ui": {"images": results},
            "result": (image,)
        }

# Registra o node no ComfyUI
NODE_CLASS_MAPPINGS = {
    "CustomImageSaver": CustomImageSaver
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CustomImageSaver": "Caesar R34 Saver"
}
