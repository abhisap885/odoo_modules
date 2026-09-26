from PIL import Image, ImageDraw

img = Image.open('/home/abhishek/Downloads/Banner.gif')
frame = img.convert('RGB')
draw = ImageDraw.Draw(frame)

# Pill to remove
pill_x = 15
pill_y = 10
pill_w = 195
pill_h = 40

draw.rectangle([pill_x, pill_y, pill_x + pill_w, pill_y + pill_h], fill=(9, 14, 22))

frame.save('test_patch5.png')
