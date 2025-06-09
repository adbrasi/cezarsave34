import os
import json
import re
# Linhas corretas
from PIL import Image
from PIL.PngImagePlugin import PngInfo
import numpy as np

class CustomImageSaver:
    version = '1.0.0'
    
    def __init__(self):
        pass
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "source": ("STRING", {"default": "", "multiline": False}),
                "title": ("STRING", {"default": "", "multiline": False}),
                "tagsfor34": ("STRING", {"default": "", "multiline": True}),
                "output_path": ("STRING", {"default": "", "multiline": False}),
                "prefix": ("STRING", {"default": "image"}),
                "number_padding": ("INT", {"default": 5, "min": 0, "max": 10}),
                "overwrite_existing": ("BOOLEAN", {"default": False}),
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
    
    def _get_next_filename(self, output_path, prefix, number_padding, ext="png"):
        """Gera o próximo nome de arquivo disponível"""
        if number_padding == 0:
            return f"{prefix}.{ext}"
        
        counter = 1
        if os.path.exists(output_path):
            existing_files = os.listdir(output_path)
            # Procura por arquivos com o mesmo prefixo
            pattern = rf"^{re.escape(prefix)}_(\d+)\.{ext}$"
            numbers = []
            for filename in existing_files:
                match = re.match(pattern, filename)
                if match:
                    numbers.append(int(match.group(1)))
            
            if numbers:
                counter = max(numbers) + 1
        
        return f"{prefix}_{counter:0{number_padding}d}.{ext}"
    
    def save_image_with_metadata(self, image, source, title, tagsfor34, output_path, prefix, number_padding, overwrite_existing):
        # Verifica se o caminho de saída foi fornecido
        if not output_path:
            raise ValueError("O caminho de saída (output_path) deve ser fornecido")
        
        # Cria o diretório se não existir
        self._create_directory(output_path)
        
        # Processa as tags
        processed_tags = self._process_tags(tagsfor34)
        
        # Prepara os metadados como JSON string
        metadata_dict = {
            "Source": source,
            "title": title,
            "tagsfor34": processed_tags
        }
        
        results = []
        
        # Processa cada imagem (caso seja um batch)
        for i, img_tensor in enumerate(image):
            # Converte tensor para numpy array e depois para PIL Image
            img_array = np.clip(255.0 * img_tensor.cpu().numpy(), 0, 255).astype(np.uint8)
            img = Image.fromarray(img_array)
            
            # Gera o nome do arquivo
            if len(image) > 1:
                # Se há múltiplas imagens, adiciona índice
                current_prefix = f"{prefix}_{i+1:0{number_padding}d}" if number_padding > 0 else f"{prefix}_{i+1}"
                filename = f"{current_prefix}.png"
            else:
                filename = self._get_next_filename(output_path, prefix, number_padding)
            
            file_path = os.path.join(output_path, filename)
            
            # Verifica se deve sobrescrever
            if not overwrite_existing and os.path.exists(file_path):
                print(f"Arquivo {file_path} já existe. Pulando...")
                continue
            
            # Cria metadados PNG
            pnginfo = PngInfo()
            
            # Adiciona cada campo de metadado separadamente
            pnginfo.add_text("Source", source)
            pnginfo.add_text("title", title)
            pnginfo.add_text("tagsfor34", processed_tags)
            
            # Também adiciona como JSON completo para compatibilidade
            pnginfo.add_text("metadata", json.dumps(metadata_dict, ensure_ascii=False))
            
            try:
                # Salva a imagem com metadados embutidos
                img.save(file_path, "PNG", pnginfo=pnginfo, optimize=False, compress_level=1)
                print(f"Imagem salva com sucesso: {file_path}")
                
                results.append({
                    "filename": filename,
                    "subfolder": "",
                    "type": "output"
                })
                
            except Exception as e:
                print(f"Erro ao salvar imagem {file_path}: {e}")
                raise
        
        # Retorna a imagem original e informações para a UI
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