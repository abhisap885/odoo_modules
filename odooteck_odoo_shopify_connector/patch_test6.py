from PIL import Image

img = Image.open('/home/abhishek/Downloads/Banner.gif')
frame = img.convert('RGB')

patch_x = 345
patch_y = 15
w = 180
h = 35
patch = frame.crop((patch_x, patch_y, patch_x + w, patch_y + h))
frame.paste(patch, (21, 15))

frame.save('test_patch6.png')
