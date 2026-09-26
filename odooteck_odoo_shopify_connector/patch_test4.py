from PIL import Image

img = Image.open('/home/abhishek/Downloads/Banner.gif')
frame = img.convert('RGB')

# Coordinates for the pill we want to remove
pill_x = 25
pill_y = 15
pill_w = 175
pill_h = 35

# Coordinates for the empty grid patch
patch_x = 330
patch_y = 15

patch = frame.crop((patch_x, patch_y, patch_x + pill_w, patch_y + pill_h))
frame.paste(patch, (pill_x, pill_y))
frame.save('test_patch4.png')
