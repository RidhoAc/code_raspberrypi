"""This example is for Raspberry Pi (Linux) only!
   It will not work on microcontrollers running CircuitPython!"""

import os
import math
import time
import requests

import numpy as np
import pygame
import busio
import board

from scipy.interpolate import griddata

from colour import Color

import adafruit_amg88xx

#library buzzer
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(23, GPIO.OUT)

i2c_bus = busio.I2C(board.SCL, board.SDA)

#url untuk mengirim data (ganti dengan ip laptop yang terdapat server)
url = "https://monitoring-temperatur-mesin.000webhostapp.com/amg/server.php"
url1 = "https://monitoring-temperatur-mesin.000webhostapp.com/config/api.php"

#pilihan_rata2 = 1, untuk rata2 4 pixel di tengah, pilihan 0, untuk rata2 semua pixel
pilihan_rata2 = 1

# temperatur terendah
MINTEMP = 26

# temperatur tertinggi
MAXTEMP = 80

# resolusi kedalaman warna
COLORDEPTH = 1024

os.putenv("SDL_FBDEV", "/dev/fb1")
# pylint: disable=no-member
pygame.init()
# pylint: enable=no-member

# initialize the sensor
sensor = adafruit_amg88xx.AMG88XX(i2c_bus)

# pylint: disable=invalid-slice-index
points = [(math.floor(ix / 8), (ix % 8)) for ix in range(0, 64)]
grid_x, grid_y = np.mgrid[0:7:32j, 0:7:32j]
# pylint: enable=invalid-slice-index

# tinggi dan lebar pixel untuk menampilkan pixel warna sensor
height = 560
width = 560

# list/rentang warna untuk color bar
colors = list(Color("blue").range_to(Color("green"), COLORDEPTH//4)) + \
         list(Color("green").range_to(Color("yellow"), COLORDEPTH//4)) + \
         list(Color("yellow").range_to(Color("red"), COLORDEPTH//4))

# membuat array warna
colors = [(int(c.red * 255), int(c.green * 255), int(c.blue * 255)) for c in colors]

#ukuran pixel warna untuk 1 pixel
displayPixelWidth = 70
displayPixelHeight = 70

#membuat tampilan dengan ukuran 560x560
lcd = pygame.display.set_mode((width, height))

lcd.fill((255, 0, 0))

pygame.display.update()
pygame.mouse.set_visible(False)

lcd.fill((0, 0, 0))
pygame.display.update()

# some utility functions
def constrain(val, min_val, max_val):
    return min(max_val, max(min_val, val))


def map_value(x, in_min, in_max, out_min, out_max):
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min


# delay selama 0.1 detik untuk menunggu sensor hidup
time.sleep(0.1)

while True:

    # membaca sensor untuk masing2 pixel sensor
    sensor_pix = sensor.pixels
    if pilihan_rata2 == 1:
        centered_pix = [sensor_pix[3][3], sensor_pix[3][4], sensor_pix[4][3], sensor_pix[4][4]]
        rata2_suhu = sum(centered_pix)/4
        rata2_suhu = round(rata2_suhu, 2)
        rata2_suhu = 0.9339*rata2_suhu + 5.4558
    else:
        #menghitung jumlah semua element pixel sensor
        total=0
        for row in sensor_pix:
            for val in row:
                total += val
        #menghitung panjang array
        n_pix=len(sensor_pix)*len(sensor_pix[0])
        rata2_suhu = total/n_pix
        rata2_suhu = round(rata2_suhu, 2)
        rata2_suhu = 0.9339*rata2_suhu + 5.4558

    #alert dari buzzer
    if rata2_suhu >= 60:
        GPIO.output(23, True)
    else:
        GPIO.output(23, GPIO.LOW)
    
    pixels = []
    for row in sensor.pixels:
        pixels = pixels + row
    pixels = [map_value(p, MINTEMP, MAXTEMP, 0, COLORDEPTH - 1) for p in pixels]

    # perform interpolation
    bicubic = griddata(points, pixels, (grid_x, grid_y), method="cubic")

    # draw everything
    for ix, row in enumerate(bicubic):
        for jx, pixel in enumerate(row):
            index = int(constrain(pixel, 0, COLORDEPTH - 1))
            color = colors[min(index, len(colors) - 1)]
            pygame.draw.rect(
                lcd,
                color,
                (
                    ix * displayPixelHeight,
                    jx * displayPixelWidth,
                    displayPixelHeight,
                    displayPixelWidth,
                ),
            )
    #pygame.image.save(lcd, os.path.join(".", f"{int(time.time())}.jpg"))
    pygame.image.save(lcd, os.path.join(".", f"suhu.jpg"))
    
    #kirim gambar dan nilai suhu ke server
    temp_str=str(rata2_suhu)
    
    with open("suhu.jpg", "rb") as image_file:
        #encode gambar ke format binary
        encoded_image = image_file.read()
        
    data = {
        "temperature": temp_str,
        "image": encoded_image
    }
    data1 = {
        "temperature": temp_str
    }
    
    #kirim data ke server
    response = requests.post(url, data=data)
    response1 = requests.post(url1, data=data1)
    
    #cek status pengiriman
    if response.status_code == 200:
        print("Data berhasil dikirim")
    else:
        print("Gagal mengirim data")
    
    
    # draw bar color disini
    barWidth = 20
    barHeight = 200
    barX = width - barWidth - 10
    barY = (height - barHeight) // 2
    
    for i in range(barHeight):
        color_idx = int(map_value(i, 0, barHeight, 0, COLORDEPTH - 1))
        if color_idx < len(colors):
            color = colors[color_idx]
            
        
        pygame.draw.rect(lcd, color[::-1], (barX, barY + i, barWidth, 1))

    # add "80C" text above the color bar
    font = pygame.font.Font(None, 30)
    text_surface = font.render("80\u00b0C", True, (255, 255, 255))
    text_rect = text_surface.get_rect()
    text_rect.center = (barX + barWidth // 2, barY - 25)
    lcd.blit(text_surface, text_rect)

    # add "26C" text below the color bar
    text_surface = font.render("26\u00b0C", True, (255, 255, 255))
    text_rect = text_surface.get_rect()
    text_rect.center = (barX + barWidth // 2, barY + barHeight + 25)
    lcd.blit(text_surface, text_rect)

    # tambahkan nilai temperatur disini
    text = "SUHU: {:.2f}\u00b0C".format(rata2_suhu)
    font = pygame.font.Font(None, 60)
    text_surface = font.render(text, True, (255, 255, 255))
    text_rect = text_surface.get_rect()
    text_rect.center = (width // 2, height - 25)
    lcd.blit(text_surface, text_rect)
    
    # tambahkan tanda plus
    text_plus = "+"
    font = pygame.font.Font(None, 30)
    text_plus_surface = font.render(text_plus, True, (255, 255, 255))
    text_plus_rect = text_plus_surface.get_rect()
    text_plus_rect.center = (width // 2, height // 2)
    lcd.blit(text_plus_surface, text_plus_rect)

    pygame.display.update()
    time.sleep(1)





