from PIL import Image as PILImage, ImageDraw

def sequence_status(steps, filled, filename, width=60, height=120):

    status_tile = PILImage.new('RGB', (width, height), (155, 155, 155, 1))
    draw = ImageDraw.Draw(status_tile)

    for step_num, step in enumerate(filled[:steps]):
        if step is None:
            color = "gray"
        else:
            color = "white"
        stepwise = height / steps
        draw.rectangle((0, stepwise * step_num, width, (stepwise * step_num) + stepwise), outline=None, fill=color)

    image_filename = '/tmp/{}.jpg'.format(filename)
    status_tile.save(image_filename)
    status_tile.close()
    return image_filename
