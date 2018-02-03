from PIL import Image as PILImage,ImageOps,ImageDraw
import random


def sequence_status(steps,filled,filename,width=60,height=120):
    w = width
    h = height
    iiimg = PILImage.new('RGB',(w,h),(155,155,155,1))
    draw = ImageDraw.Draw(iiimg)
    #steps = 6
    #either [(x0, y0), (x1, y1)] or [x0, y0, x1, y1].
    #filled = [2,5,8]
    for i,step in enumerate(range(steps)):
        #color = random.choice(["gray","white"])
        if i in filled:
            color = "white"
        else:
            color = "gray"
        print(i,color)
        stepwise = h/steps
        draw.rectangle((0,stepwise*i,w,(stepwise*i)+stepwise), outline=None,fill=color)

    filename = '{}.jpg'.format(filename)
    iiimg.save(filename)
    iiimg.close()
    return filename