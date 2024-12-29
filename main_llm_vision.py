import os
import sys
import math
import pygame
import numpy as np
from PIL import Image
import base64
import json
import time
from openai import OpenAI
import google.generativeai as genai
import PIL.Image

MIN_STEP = 20
MAX_STEP = 150
MIN_ANGLE = 0
MAX_ANGLE = 360
SCALE_OBJ = 3

BACKGROUND_COLOR = (0, 0, 0)    
TARGET_COLOR = (255, 255, 255)     
OBSTACLE_COLOR = (255, 0, 0)    
TEXT_COLOR = (255, 255, 255)    
PATH_COLOR = (255, 255, 255) 

OBSTACLE_RADIUS = 15
OBSTACLE_QTY = 0
END_KEYS = [pygame.K_ESCAPE]
DISTANCE_THRESHOLD = 60
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 600
FPS = 30  

class Car:
    def __init__(self, x, y, image_path, initial_angle=0):
        self.x = x
        self.y = y
        self.font = pygame.font.Font(None, 20)
        self.angle = initial_angle
        self.original_image = pygame.image.load(image_path).convert_alpha()
        width = self.original_image.get_width()
        height = self.original_image.get_height()
        self.original_image = pygame.transform.scale(
            self.original_image,
            (width // SCALE_OBJ, height // SCALE_OBJ)
        )
        self.original_image = pygame.transform.rotate(self.original_image, -90)
        self.image = self.original_image
        self.rect = self.image.get_rect(center=(self.x, self.y))
        self.mission = False

    def turn(self, angle):
        self.angle = angle

    def move(self, step):
        rad = math.radians(self.angle)
        self.x += step * math.cos(rad)
        self.x = max(50, min(self.x, WINDOW_WIDTH-50))
        self.y -= step * math.sin(rad)
        self.y = max(50, min(self.y, WINDOW_HEIGHT-50))

    def draw(self, screen, car_msg):
        rotated_image = pygame.transform.rotate(self.original_image, self.angle)
        self.rect = rotated_image.get_rect(center=(self.x, self.y))
        screen.blit(rotated_image, self.rect)
        label_surface = self.font.render(car_msg, True, TEXT_COLOR)
        label_rect = label_surface.get_rect(midtop=(self.x - 80, self.y + 10))
        screen.blit(label_surface, label_rect)

class StrategyGame:
    def __init__(self, width=WINDOW_WIDTH, height=WINDOW_HEIGHT, counter_openai=0, counter_gemini=0):

        os.environ['SDL_VIDEO_WINDOW_POS'] = "%d,%d" % (450,50)
        self.counter_openai = counter_openai
        self.counter_gemini = counter_gemini
        pygame.init()
        self.width = width
        self.height = height
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Car Strategy Game")
        self.clock = pygame.time.Clock()
        self.is_running = True
        
        self.car_1 = Car(TARGET_CAR_1_X, TARGET_CAR_1_Y, "car1.png")
        self.car_2 = Car(TARGET_CAR_2_X, TARGET_CAR_2_Y, "car2.png")
        self.target_x = TARGET_X
        self.target_y = TARGET_Y
        self.font = pygame.font.Font(None, 40)
        self.mission_accomplished = False
        self.mission_failed = False
        self.counter = 0
        
        #self.obstacles = [(self.width // 2, self.height // 2)]
        self.obstacles = []
        
        self.path_1 = [(self.car_1.x, self.car_1.y)]
        self.path_2 = [(self.car_2.x, self.car_2.y)]

        openai_api_key = os.getenv("OPENAI_API_KEY")
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        
        self.client = OpenAI(api_key=openai_api_key)
        genai.configure(api_key=gemini_api_key)
    
    def handle_events(self):
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.is_running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in END_KEYS:
                        self.is_running = False
                    if event.key == pygame.K_q:
                        self.is_running = False

    def query_openai_vision(self):
        
        def encode_image(image_path):
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode("utf-8")
        
        base64_image = encode_image("screenshot.jpg")
                
        user_message = (            
                    f"locate in the screenshot: \n"
                    f"2- the OPENAI blue vehicle\n" 
                    f"3- the GEMINI red vehicle\n"
                    f"4- the target is the white circle\n"
                    f"Objective is to hit exactly the white circle target faster than the competitor vehicle\n"
                    f"Please respond ONLY with valid JSON in this exact format:\n"
                    f'{{"direction": <str>, "steps": <integer>}}\n'
                    f"The steps count must be between {MIN_STEP} and {MAX_STEP}.\n"
                    f"The direction must be: left, right, up or down.\n"
                    f"the provided screenshot has black background\n"               
                )
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user", 
                    "content": [
                        {"type": "text", "text": user_message + "your vehicle is the OPENAI blue one\n"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}",
                                },
                        },
                    ],
                }
            ],
        )
        
        file1_gemini = PIL.Image.open("screenshot.jpg")
        model_gemini = genai.GenerativeModel(model_name="gemini-1.5-flash")
        prompt_gemini = user_message + "your vehicle is the GEMINI red one\n"
        response_gemini = model_gemini.generate_content([prompt_gemini, file1_gemini])

        content_openai = response.choices[0].message.content
        content_openai = content_openai.strip().strip("```").strip("json").strip()
        
        content_gemini = str(response_gemini.text).strip().strip("```").strip("json").strip()
        
        try:
            movement_openai = json.loads(content_openai)
            direction_openai = movement_openai.get("direction", 0)
            steps_openai = movement_openai.get("steps", 0)
            print("OpenAI defined direction:", direction_openai)
            print("OpenAI defined steps:", steps_openai)
            
            movement_gemini = json.loads(content_gemini)
            direction_gemini = movement_gemini.get("direction", 0)
            steps_gemini = movement_gemini.get("steps", 0)
            print("\nGEMINI defined direction:", direction_gemini)
            print("GEMINI defined steps:", steps_gemini)
            
            if direction_openai == "left":
                angle_openai = 180
            elif direction_openai == "right":
                angle_openai = 0
            elif direction_openai == "up":
                angle_openai = 90
            elif direction_openai == "down":
                angle_openai = 270

            if direction_gemini == "left":
                angle_gemini = 180
            elif direction_gemini == "right":
                angle_gemini = 0
            elif direction_gemini == "up":
                angle_gemini = 90
            elif direction_gemini == "down":
                angle_gemini = 270
            
            return angle_openai, angle_gemini, steps_openai, steps_gemini
            
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON response: {e}")
            return 0, 0

    def update_car_movement(self):
        """Capture a screenshot, save it, send it to the model, and move the car."""
        screenshot = pygame.surfarray.array3d(self.screen)
        screenshot = np.rot90(screenshot)
        screenshot = np.flipud(screenshot)
        image = Image.fromarray(screenshot)
        image.save("screenshot.jpg", format="JPEG")
        
        angle_car_1, angle_car_2, steps_car_1, steps_car_2 = self.query_openai_vision()
        
        self.car_1.turn(angle_car_1)
        self.car_1.move(steps_car_1)
        self.car_2.turn(angle_car_2)
        self.car_2.move(steps_car_2)
        
        self.path_1.append((self.car_1.x, self.car_1.y))
        self.path_2.append((self.car_2.x, self.car_2.y))

    def draw_target(self):
        line_length = 20
        pygame.draw.circle(self.screen, TARGET_COLOR, (self.target_x, self.target_y), 35)
        label_surface = self.font.render("Target", True, TEXT_COLOR)
        label_rect = label_surface.get_rect(midtop=(self.target_x, self.target_y + line_length + 20))
        self.screen.blit(label_surface, label_rect)

    def draw_obstacles(self):
        """Draw red circles representing obstacles."""
        for x, y in self.obstacles:
            pygame.draw.circle(self.screen, OBSTACLE_COLOR, (x, y), OBSTACLE_RADIUS)
            line_length = 20
            label_surface = self.font.render("Obstacle", True, OBSTACLE_COLOR)
            label_rect = label_surface.get_rect(midtop=(x, y + line_length + 10))
            self.screen.blit(label_surface, label_rect)
            
    def draw_path(self):
        if len(self.path_1) > 1:
            pygame.draw.lines(self.screen, PATH_COLOR, False, self.path_1, 1)
        if len(self.path_2) > 1:
            pygame.draw.lines(self.screen, PATH_COLOR, False, self.path_2, 1) 

    def check_collisions(self, car):
        """Check if the car collides with any obstacles."""
        self.car = car
        for x, y in self.obstacles:
            dist_x = self.car.x - x
            dist_y = self.car.y - y
            distance = math.sqrt(dist_x**2 + dist_y**2)
            if distance < OBSTACLE_RADIUS + 30:
                self.mission_failed = True
                        
    def update(self, car):
        self.car = car
        if not self.mission_failed and not self.mission_accomplished:
            self.check_collisions(self.car)
            
        """Check if the car has reached the target."""
        dist_x = self.car.x - self.target_x
        dist_y = self.car.y - self.target_y
        distance = math.sqrt(dist_x**2 + dist_y**2)
        if distance < DISTANCE_THRESHOLD:
            self.mission_accomplished = True
            self.car.mission = True

    def draw_message(self, message):
        text_surface = self.font.render(message, True, TEXT_COLOR)
        text_rect = text_surface.get_rect(center=(self.width // 2, self.height // 9))
        self.screen.blit(text_surface, text_rect)
        
    def draw(self):
        counter = self.counter
        self.screen.fill(BACKGROUND_COLOR)
        
        self.draw_obstacles()
        self.draw_path()
        self.draw_target()
        self.car_1.draw(self.screen, car_msg = "OPENAI")
        self.car_2.draw(self.screen, car_msg = "GEMINI")
            
        if counter > 34:
            self.mission_failed = True
            
        if self.car_1.mission == True and self.car_2.mission == True:
            self.draw_message("Both cars reached the target at the same time")
            time.sleep(2)
        elif self.car_1.mission == True:
            self.draw_message("OpenAI won the game with " + str(counter) + " iterations")
            time.sleep(2)
            self.counter_openai = self.counter_openai + 1
        elif self.car_2.mission == True:
            self.draw_message("GEMINI won the game with " + str(counter) + " iterations")
            time.sleep(2)
            self.counter_gemini = self.counter_gemini + 1
        elif self.mission_failed:
            time.sleep(2)
            self.draw_message("Mission Failed")       
            
        pygame.display.flip()

    def run(self):
        """Main game loop."""
        
        while self.is_running and not self.mission_accomplished and not self.mission_failed:
            self.counter = self.counter + 1
            time.sleep(5)
            print("Iteration:",self.counter,"\n") 
            self.clock.tick(FPS)
            self.handle_events()
            self.update(self.car_1)
            self.update(self.car_2)
            self.draw()
            self.update_car_movement()
        
        pygame.quit()
        return self.counter_openai, self.counter_gemini
            

if __name__ == "__main__":
    counter = 0
    counter_openai = 0
    counter_gemini = 0
    total_openai = 0
    total_gemini = 0
    
    TARGET_X = 800  
    TARGET_Y = 300
    TARGET_CAR_1_X = 100
    TARGET_CAR_1_Y = 100
    TARGET_CAR_2_X = 100
    TARGET_CAR_2_Y = 500
    while counter < 5:
        game = StrategyGame(counter_openai=counter_openai, counter_gemini=counter_gemini)
        counter_openai, counter_gemini = game.run()
        counter = counter + 1

    print("\nOpenAI wins:", counter_openai)
    print("GEMINI wins:", counter_gemini)
    total_openai = total_openai + counter_openai
    total_gemini = total_gemini + counter_gemini
    
    time.sleep(10)
    TARGET_CAR_1_X = 100
    TARGET_CAR_1_Y = 500
    TARGET_CAR_2_X = 100
    TARGET_CAR_2_Y = 100
    counter = 0
    counter_openai = 0
    counter_gemini = 0
    while counter < 5:
        game = StrategyGame(counter_openai=counter_openai, counter_gemini=counter_gemini)
        counter_openai, counter_gemini = game.run()
        counter = counter + 1

    print("\nOpenAI wins:", counter_openai)
    print("GEMINI wins:", counter_gemini)
    total_openai = total_openai + counter_openai
    total_gemini = total_gemini + counter_gemini
    
    time.sleep(10)
    TARGET_X = 200  
    TARGET_Y = 300
    TARGET_CAR_1_X = 900
    TARGET_CAR_1_Y = 100
    TARGET_CAR_2_X = 900
    TARGET_CAR_2_Y = 500
    counter = 0
    counter_openai = 0
    counter_gemini = 0
    while counter < 1:
        game = StrategyGame(counter_openai=counter_openai, counter_gemini=counter_gemini)
        counter_openai, counter_gemini = game.run()
        counter = counter + 1

    print("\nOpenAI wins:", counter_openai)
    print("GEMINI wins:", counter_gemini)
    total_openai = total_openai + counter_openai
    total_gemini = total_gemini + counter_gemini
    
    time.sleep(10)
    TARGET_CAR_1_X = 900
    TARGET_CAR_1_Y = 500
    TARGET_CAR_2_X = 900
    TARGET_CAR_2_Y = 100
    counter = 0
    counter_openai = 0
    counter_gemini = 0
    while counter < 1:
        game = StrategyGame(counter_openai=counter_openai, counter_gemini=counter_gemini)
        counter_openai, counter_gemini = game.run()
        counter = counter + 1

    print("\nOpenAI wins:", counter_openai)
    print("GEMINI wins:", counter_gemini)
    total_openai = total_openai + counter_openai
    total_gemini = total_gemini + counter_gemini
    
    time.sleep(10)
    TARGET_X = 500  
    TARGET_Y = 200
    TARGET_CAR_1_X = 100
    TARGET_CAR_1_Y = 500
    TARGET_CAR_2_X = 900
    TARGET_CAR_2_Y = 500
    counter = 0
    counter_openai = 0
    counter_gemini = 0
    while counter < 1:
        game = StrategyGame(counter_openai=counter_openai, counter_gemini=counter_gemini)
        counter_openai, counter_gemini = game.run()
        counter = counter + 1

    print("\nOpenAI wins:", counter_openai)
    print("GEMINI wins:", counter_gemini)
    total_openai = total_openai + counter_openai
    total_gemini = total_gemini + counter_gemini
    
    time.sleep(10)
    TARGET_CAR_1_X = 900
    TARGET_CAR_1_Y = 500
    TARGET_CAR_2_X = 100
    TARGET_CAR_2_Y = 500
    counter = 0
    counter_openai = 0
    counter_gemini = 0
    while counter < 5:
        game = StrategyGame(counter_openai=counter_openai, counter_gemini=counter_gemini)
        counter_openai, counter_gemini = game.run()
        counter = counter + 1
    
    print("\nOpenAI wins:", counter_openai)
    print("GEMINI wins:", counter_gemini)
    total_openai = total_openai + counter_openai
    total_gemini = total_gemini + counter_gemini
    
    print("\nTotal OpenAI wins:", total_openai)
    print("Total GEMINI wins:", total_gemini)
    
    sys.exit()
