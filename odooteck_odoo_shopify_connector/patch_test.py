from PIL import Image
img = Image.open('/home/abhishek/Downloads/Banner.gif')
img.seek(0)
frame = img.convert('RGB')

# Pill looks like it's from x=20 to x=220, y=10 to y=50. Let's make it a bit wider: x=10 to x=250, y=10 to y=60
# Let's grab a patch from x=350, y=10 to x=590, y=60
patch = frame.crop((350, 10, 590, 60))
frame.paste(patch, (20, 10))

# What about the body text? "Engineered natively for Odoo 19."
# Let's just leave it if they only asked for the top one, or replace "19" with "20".
# It's hard to edit text seamlessly in a raster image, but if they specifically said "uper odoo19 enterprice likha hai wo na ho" (the one written on top), we just remove that.

frame.save('test_patch.png')
