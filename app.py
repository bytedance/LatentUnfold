 '''
 Copyright (c) 2024 Bytedance Ltd. and/or its affiliates

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
 '''
 
import os
import gradio as gr
import torch
from PIL import Image
from typing import *
import ast
import numpy as np
import yaml

from utils.seg_utils import rmbg
from utils.image_utils import resize
from utils.prompt_utils import gpt, setup_gpt_config
from latent_unfold.latent_unfold import LatentUnfoldPipeline
from latent_unfold.register import init_pipeline


pipeline = None
config = {
    "gpt": {
        "base_url": "",
        "api_version": "",
        "ak": "",
        "model_name": ""
    },
    "base_model": "black-forest-labs/FLUX.1-dev",
    "seg_model": "briaai/RMBG-2.0"
}

def prepare_pipeline(aug_att=0.0, grid_shape=(3,3), image_shape=(512,512), cascade=(2,3,4)):
    pipe = LatentUnfoldPipeline.from_pretrained( 
        config.get("base_model"),
        torch_dtype=torch.bfloat16,
    )
    pipe.to("cuda", torch.bfloat16)
    pipe = init_pipeline(pipe, aug_att=aug_att, grid_shape=grid_shape, image_shape=image_shape, cascade=cascade) 
    return pipe


def generate_image(images: List[Tuple[Image.Image, str]],
                   user_prompt,
                   generate_long_prompt_with_gpt,
                   long_prompt,
                    width,
                    height,
                    strength,
                    num_inference_steps, 
                    guidance_scale,
                    seed,
                    base_url,
                    api_version,
                    model_name, 
                    ak,
                    aug_att,
                    grid_shape,
                    cascade):
    if len(images) == 0:
        gr.Error("Please upload input images.")
        return gr.update()
    
    if seed == 0:
        seed = torch.seed() & 0xFFFFFFFF

    if grid_shape == "3x3":
        grid_shape = (3,3)
    else:
        grid_shape = (2,2)

    if cascade == "2,3":
        cascade = (2,3)
    elif cascade == "2":
        cascade = (2,)
    else:
        cascade = (2,3,4)

    test_images = []
    for image, name in images:
        test_img_rmbg = rmbg(image, config.get("seg_model"))
        test_img_rmbg = resize(test_img_rmbg)
        test_images.append(test_img_rmbg)

    if generate_long_prompt_with_gpt:
        setup_gpt_config(base_url=base_url,
                         api_version=api_version,
                         ak=ak, 
                         model_name=model_name)
        
        test_gpt_prompt = gpt(test_images[0])
        short_prompt = f"{test_gpt_prompt['summary']} [IMAGE1] {user_prompt}"
        long_prompt = f"{short_prompt} [IMAGE2]{test_gpt_prompt['row1']['image2']} [IMAGE3]{test_gpt_prompt['row1']['image3']} [IMAGE4]{test_gpt_prompt['row2']['image1']} [IMAGE5]{test_gpt_prompt['row2']['image2']} [IMAGE6]{test_gpt_prompt['row2']['image3']} [IMAGE7]{test_gpt_prompt['row3']['image1']} [IMAGE8]{test_gpt_prompt['row3']['image2']} [IMAGE9]{test_gpt_prompt['row3']['image3']}"
    else:
        long_prompt = long_prompt.replace("{user_prompt}", user_prompt)
    print(long_prompt)

    try:
    
        generator = torch.Generator().manual_seed(seed)
        output_image = pipeline(prompt=long_prompt,
            image=test_images, # supports multi-view, single-view
            num_images_per_prompt=1, 
            height=height, 
            width=width, 
            mask_image=None, 
            strength=strength, 
            num_inference_steps=num_inference_steps, 
            guidance_scale=guidance_scale,
            generator=generator,
            mosaic_shape=grid_shape,
            seed=seed).images[0]
    except Exception as e:
        print(e)
        gr.Error(f"An error occurred: {e}")
        return gr.update()


    return gr.update(value = output_image, label=f"Generated Image, seed = {seed}")

sample_list = [
        [['assets/clock04.jpg'],
         'In a Bauhaus style room, this item is placed on a shiny glass table, with a vase of flowers next to it. In the afternoon sun, the shadows of the blinds are cast on the wall.', 
         "",
         True,
        ],
        [['assets/rc_car02.jpg', 'assets/rc_car03.jpg', 'assets/rc_car04.jpg'],
         'A film style shot. On the moon, this item drives across the moon surface. The background is that Earth looms large in the foreground.', 
         "",
         True,
        ],
        [['assets/clock04.jpg'],
         'In a Bauhaus style room, this item is placed on a shiny glass table, with a vase of flowers next to it. In the afternoon sun, the shadows of the blinds are cast on the wall.', 
         "This set of full-frame photos captures an identical bright yellow alarm clock subject firmly positioned in the real scene, highlighting its retro design, vibrant color, and metal construction from various perspectives (cinematic, epic, 4K, high quality). [IMAGE1]{user_prompt} [IMAGE2]captures the white clock face with black numerals and a large yellow '3' on the right. [IMAGE3]displays the silver metal feet and the glossy yellow finish of the clock's body. [IMAGE4]presents a close-up of the clock's hands, showing the sleek silver design. [IMAGE5]focuses on the clock's side profile, emphasizing the curved yellow frame. [IMAGE6]shows the top view, highlighting the shiny metal handle and bell structure. [IMAGE7]captures the clock's back, revealing the battery compartment and adjustment knobs. [IMAGE8]features the clock's overall shape, showcasing its retro design and vibrant color. [IMAGE9]emphasizes the clock's sturdy metal construction and polished finish.",
         False,
        ],
        [['assets/rc_car02.jpg', 'assets/rc_car03.jpg', 'assets/rc_car04.jpg'],
         'A film style shot. On the moon, this item drives across the moon surface. The background is that Earth looms large in the foreground.', 
         "This set of full-frame photos captures an identical colorful toy car subject firmly positioned in the real scene, highlighting its vibrant design, number '1' badge, and playful features from various perspectives (cinematic, epic, 4K, high quality). [IMAGE1] {user_prompt} [IMAGE2]captures the toy car's front view, showcasing the number '1' badge and colorful details. [IMAGE3]displays the toy car's side, focusing on the black wheels and number '1' sticker. [IMAGE4]presents the toy car's rear, showing the smooth curves and bright color scheme. [IMAGE5]showcases the toy car's antenna, emphasizing its orange color and blue tip. [IMAGE6]features the toy car's interior, highlighting the blue and red driver figure with a helmet. [IMAGE7]focuses on the toy car's bottom, displaying the green base and textured surface. [IMAGE8]captures the toy car's overall shape and color scheme, providing a comprehensive view. [IMAGE9]features the structure and texture of the subject.",
         False,
        ]
    ]

def pre_process_samples():
    sample_list_display = []
    for sample in sample_list:
        # the image files.
        sample.append(sample[0])

        # load image for display
        image_files = sample[0]
        images = []
        for image_file in image_files:
            img = Image.open(image_file)
            W, H = img.size
            img = img.resize((int(W / H * 512), 512))
            images.append(np.array(img))

        if len(images) == 1:
            sample[0] = Image.fromarray(images[0])
        elif len(images) > 4:
            raise NotImplementedError("Only support up to 4 images per sample.")
        elif len(images) < 1:
            raise ValueError("No images found.")
        else:
            # Pad images to make them the same size
            images += [np.zeros_like(images[0])] * (4 - len(images))

            # Stack images row-wise
            cols = 2
            rows = 2
            grid_rows = [np.hstack(images[i*cols:(i+1)*cols]) for i in range(rows)]
            # Stack all rows vertically
            grid = np.vstack(grid_rows)
        
            sample[0] = grid

        sample_list_display.append(sample)
    return sample_list_display
    

def process_samples(input_image, prompt_text, long_prompt_text, generate_long_prompt_with_gpt, image_files):
    images = []
    parsed_list = ast.literal_eval(image_files)
    for image_file in parsed_list:
        image = Image.open(image_file)
        images.append((image, image_file))
    return images

def on_advanced_settings_change(aug_att, grid_type, cascade, image_width, image_height):
    global pipeline
    grid_shape = (3,3) if grid_type == "3x3" else (2,2)
    cascade = (2,3) if cascade == "2,3" else (2,) if cascade == "2" else (2,3,4)
    print(aug_att, grid_type, cascade, image_width, image_height)
    pipeline = init_pipeline(pipeline, aug_att=aug_att, grid_shape=grid_shape, image_shape=(image_height, image_width), cascade=cascade) 
    return

CSS = """
.gr-image-full-view img {
    width: 100%;
    height: 100%;
    object-fit: contain;
}
"""

with gr.Blocks(css=CSS) as demo:
    gr.HTML("""
    <div style="text-align: center; max-width: 650px; margin: 0 auto;">
        <h1 style="font-size: 1.5rem; font-weight: 700; display: block;">Flux Already Knows -- Activating Subject-Driven Image Generation without Training</h1>
        <h2 style="font-size: 1.2rem; font-weight: 300; margin-bottom: 1rem; display: block;">Gradio Demo</h2>
    </div>
    """)
    
    gr.Markdown("""
    ### How to use:
    Upload one or more images of the same object.

    If you have an OpenAI API key (preferred), enter it under <strong>GPT Config</strong>, then check <strong>Generate Long Prompt with GPT</strong>. You only need to enter a <strong>User Prompt</strong>.

    If you don’t have an OpenAI API key, you’ll need to enter a <strong>User Prompt</strong>, and manually create the <strong>Long Prompt</strong> based on the last two examples.
    """)
    
    with gr.Row():
        with gr.Column(scale=3):
            with gr.Row():
                ui_input_images = gr.Gallery(label="Input Image", type="pil", scale = 3, height = 480, min_width=100)
                # HACK, gr.Examples doesn't work with gr.Gallery correctly.
                # using a dummy image for displaying gr.Examples
                ui_dummy_image = gr.Image(label="Input Image", visible=False, elem_classes="gr-image-full-view")
                ui_dummy_text = gr.Textbox(label="Image Files", visible=False)
            ui_prompt_text = gr.Textbox(label="User Prompt", value="")
            ui_gpt_check_box = gr.Checkbox(label="Generate Long Prompt with GPT", value=True)
            ui_long_prompt_text = gr.Textbox(label="Long Prompt", value="", visible=False)

            ui_btn_generate = gr.Button("Generate")
            with gr.Accordion("Advanced", open=False):
                with gr.Row():
                    ui_num_inference_steps = gr.Number(label="num steps", value=28)
                    ui_seed = gr.Number(label="seed", value=0)
                with gr.Row():
                    ui_width = gr.Number(label="width", value=512)
                    ui_height = gr.Number(label="height", value=512)
                with gr.Row():
                    ui_guidance_scale = gr.Number(label="guidance scale", value=7)
                    ui_strength = gr.Number(label="strength", value=1)
                with gr.Row():
                    ui_aug_att = gr.Number(label="aug_att (0.00, 0.02, 0.05 etc.)", value=0)
                    ui_grid_type = gr.Dropdown(label="grid type", choices=["3x3", "2x2"], value="3x3")
                with gr.Row():
                    ui_cascade = gr.Dropdown(label="cascade", choices=["2", "2,3", "2,3,4"], value="2,3,4")

            advanced_components = [ui_aug_att, ui_grid_type, ui_cascade, ui_width, ui_height]
            for comp in advanced_components:
                comp.change(fn=on_advanced_settings_change, inputs=advanced_components, outputs=[])

            with gr.Accordion("GPT Config", open=False):
                ui_gpt_base_endpoint = gr.Textbox(label="Endpoint", value=config.get("gpt", {}).get("base_url", ""))
                ui_api_version = gr.Textbox(label="API Version", value=config.get("gpt", {}).get("api_version", ""))
                ui_gpt_model_version = gr.Textbox(label="Model version", value=config.get("gpt", {}).get("model_name", ""))
                ui_ak = gr.Textbox(label="Access Key", value=config.get("gpt", {}).get("ak", ""))

        with gr.Column(scale=2):
            image_output = gr.Image(label="Generated Image", elem_classes="gr-image-full-view", interactive=False, height=500)

    gr.Examples(examples=pre_process_samples(), 
                inputs=[ui_dummy_image, ui_prompt_text, ui_long_prompt_text, ui_gpt_check_box, ui_dummy_text],
                outputs=[ui_input_images],
                fn=process_samples,
                run_on_click=True,
                )
    
    ui_gpt_check_box.change(
        lambda x: gr.update(visible= x is not True),
        inputs=[ui_gpt_check_box],
        outputs=[ui_long_prompt_text]
    )

    ui_btn_generate.click(generate_image, inputs=[ui_input_images, 
                                                    ui_prompt_text, 
                                                    ui_gpt_check_box,
                                                    ui_long_prompt_text,
                                                    ui_width,
                                                    ui_height,
                                                    ui_strength,
                                                    ui_num_inference_steps, 
                                                    ui_guidance_scale, 
                                                    ui_seed,
                                                    ui_gpt_base_endpoint,
                                                    ui_api_version,
                                                    ui_gpt_model_version,
                                                    ui_ak,
                                                    ui_aug_att,
                                                    ui_grid_type,
                                                    ui_cascade],
                                          outputs=[image_output], concurrency_id="gpu")

if __name__ == "__main__":
    aug_att = 0.00 # 0.00, 0.02, 0.05
    grid_shape = (3,3) 
    image_shape = (512,512)
    cascade = (2,3,4) # (2,), (2,3), (2,3,4)
    pipeline = prepare_pipeline(aug_att=aug_att, grid_shape=grid_shape, image_shape=image_shape, cascade=cascade)

    demo.queue()
    local_url, share_url = demo.launch()
