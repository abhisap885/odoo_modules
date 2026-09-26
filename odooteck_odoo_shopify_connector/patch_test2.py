from PIL import Image, ImageDraw

img = Image.open('/home/abhishek/Downloads/Banner.gif')
img.seek(0)
frame = img.convert('RGB')
draw = ImageDraw.Draw(frame)

# Inspect pixels to find bg color and grid color
bg_col = frame.getpixel((380, 25))
grid_col = frame.getpixel((390, 25)) # just guessing

print("BG:", bg_col)
print("Grid:", grid_col)

# Let's just crop a 130x50 block from (360, 10) and paste it multiple times
patch = frame.crop((360, 10, 490, 60))
frame.paste(patch, (10, 10))
frame.paste(patch, (140, 10)) # to cover up to x=270, wait, it might cover the 2nd pill

# The 2nd pill "REST & GraphQL API" starts around x=205
# Let's only paste up to x=200
# Crop patch exactly to the width of the pill we want to cover.
# Let's say pill is x=25 to x=195.
patch = frame.crop((360, 10, 360 + (195 - 25), 60))
frame.paste(patch, (25, 10))

frame.save('test_patch2.png')
