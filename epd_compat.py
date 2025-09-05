import platform

arch = platform.machine()

if arch == "aarch64":
    # Real hardware import
    from waveshare_epd import epd7in5bc as real_epd7in5bc
    epd7in5bc = real_epd7in5bc
else:
    # Simulation stub
    from PIL import Image
    import os
    import logging

    class SimEPD:
        width = 640
        height = 384
        def init(self):
            logging.info("Simulated EPD init")
        def Clear(self):
            logging.info("Simulated EPD clear")
        def getbuffer(self, image):
            # In simulation, just return the image itself
            return image
        def display(self, black, red):
            # Combine black and red layers into a single image
            os.makedirs("sim_output", exist_ok=True)
            combined = Image.new("RGB", (self.width, self.height), (255, 255, 255))
            # Paste black layer
            for y in range(self.height):
                for x in range(self.width):
                    if black.getpixel((x, y)) == 0:
                        combined.putpixel((x, y), (0, 0, 0))
            # Paste red layer
            for y in range(self.height):
                for x in range(self.width):
                    if red.getpixel((x, y)) == 0:
                        combined.putpixel((x, y), (160, 0, 0))
            combined.save("sim_output/combined.bmp", "BMP")
            logging.info("Simulated display: combined.bmp written")
        def sleep(self):
            logging.info("Simulated EPD sleep")

    class SimEpd7in5bc:
        EPD = SimEPD

    epd7in5bc = SimEpd7in5bc
