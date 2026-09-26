from PIL import Image

img = Image.open('/home/abhishek/Downloads/Banner.gif')
frame = img.convert('RGB')

patch_x = 381
patch_y = 15
patch = frame.crop((patch_x, patch_y, patch_x + 72, patch_y + 35))

frame.paste(patch, (21, 15))
frame.paste(patch, (93, 15))
frame.paste(patch.crop((0, 0, 36, 35)), (165, 15))

# Let's also black out the tiny part from x=15 to x=21 using edge color
edge_patch = frame.crop((375, 15, 381, 50))
frame.paste(edge_patch, (15, 15))

frame.save('test_patch7.png')
