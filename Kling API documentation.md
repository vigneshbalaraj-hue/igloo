# Image to video

Search

* Get Started  
  * [Overview](https://kling.ai/document-api/quickStart%2FproductIntroduction%2Foverview)  
  * [Quick Start](https://kling.ai/document-api/quickStart%2FuserManual)  
  * [Changelog](https://kling.ai/document-api/apiReference%2FupdateNotice)  
* API Reference  
  * [General Info](https://kling.ai/document-api/apiReference%2FcommonInfo)  
  * [Rate Limits](https://kling.ai/document-api/apiReference%2FrateLimits)  
  * [Callback Schema](https://kling.ai/document-api/apiReference%2FcallbackProtocol)  
  * Video Generation  
    * [Models](https://kling.ai/document-api/apiReference%2Fmodel%2FvideoModels)  
    * [Video Omni](https://kling.ai/document-api/apiReference%2Fmodel%2FOmniVideo)  
    * [Text to Video](https://kling.ai/document-api/apiReference%2Fmodel%2FtextToVideo)  
    * [Image to Video](https://kling.ai/document-api/apiReference%2Fmodel%2FimageToVideo)  
    * [Reference to Video](https://kling.ai/document-api/apiReference%2Fmodel%2FmultiImageToVideo)  
    * [Motion Control](https://kling.ai/document-api/apiReference%2Fmodel%2FmotionControl)  
    * [Multi-elements to video](https://kling.ai/document-api/apiReference%2Fmodel%2FmultiElements)  
    * [Extend Video](https://kling.ai/document-api/apiReference%2Fmodel%2FvideoExtension)  
    * [Lip Sync](https://kling.ai/document-api/apiReference%2Fmodel%2FlipSync)  
    * [Avatar](https://kling.ai/document-api/apiReference%2Fmodel%2Favatar)  
    * [Text to Audio](https://kling.ai/document-api/apiReference%2Fmodel%2FtextToAudio)  
    * [Video to Audio](https://kling.ai/document-api/apiReference%2Fmodel%2FvideoToAudio)  
    * [Text to Speech](https://kling.ai/document-api/apiReference%2Fmodel%2FTTS)  
    * [Voice Clone](https://kling.ai/document-api/apiReference%2Fmodel%2FcustomVoices)  
    * [Image Recognize](https://kling.ai/document-api/apiReference%2Fmodel%2FimageRecognize)  
    * [Element](https://kling.ai/document-api/apiReference%2Fmodel%2Felement)  
  * Effects  
    * [Effect TemplatesNEW](https://kling.ai/document-api/quickStart%2FproductIntroduction%2FeffectsCenter)  
    * [Video Effects](https://kling.ai/document-api/apiReference%2Fmodel%2FvideoEffects)  
  * Image Generation  
    * [Models](https://kling.ai/document-api/apiReference%2Fmodel%2FimageModels)  
    * [Image Omni](https://kling.ai/document-api/apiReference%2Fmodel%2FOmniImage)  
    * [Image Generation](https://kling.ai/document-api/apiReference%2Fmodel%2FimageGeneration)  
    * [Reference to Image](https://kling.ai/document-api/apiReference%2Fmodel%2FmultiImageToImage)  
    * [Extend Image](https://kling.ai/document-api/apiReference%2Fmodel%2FimageExpansion)  
    * [AI Multi-Shot](https://kling.ai/document-api/apiReference%2Fmodel%2FaiMultiShot)  
    * [Virtual Try-On](https://kling.ai/document-api/apiReference%2Fmodel%2FvirtualTryOn)  
  * Others  
    * [Query user info](https://kling.ai/document-api/apiReference%2FaccountInfoInquiry)  
* Pricing  
  * [Billing Info](https://kling.ai/document-api/productBilling%2FbillingMethod)  
  * [Prepaid Resource Packs](https://kling.ai/document-api/productBilling%2FprePaidResourcePackage)  
* Protocols  
  * [Privacy Policy of API Service](https://kling.ai/document-api/protocols%2FprivacyPolicy)  
  * [Terms of API Service](https://kling.ai/document-api/protocols%2FpaidServiceProtocol)  
  * [API Service Level Agreement](https://kling.ai/document-api/protocols%2FpaidLevelProtocol)

# **Image to Video**

---

## **Create Task**

POST/v1/videos/image2video

💡

Please note that in order to maintain naming consistency, the original model field has been changed to model\_name. Please use this field to specify the model version in the future.  
We maintain backward compatibility. If you continue using the original model field, it will not affect API calls and will be equivalent to the default behavior when model\_name is empty (i.e., calling the V1 model).

### **Request Header**

Content-TypestringRequiredDefault to application/json

Data Exchange Format

AuthorizationstringRequired

Authentication information, refer to API authentication

### **Request Body**

model\_namestringOptionalDefault to kling-v1

Model Name

Enum values：kling-v1kling-v1-5kling-v1-6kling-v2-masterkling-v2-1kling-v2-1-masterkling-v2-5-turbokling-v2-6kling-v3

imagestringOptional

Reference Image

* Supports image Base64 encoding or image URL (ensure accessibility)  
* Important: When using Base64, do NOT add any prefix like data:image/png;base64,. Submit only the raw Base64 string.  
* Correct Base64 format:  
* Incorrect Base64 format (with data: prefix):  
* Supported image formats: .jpg / .jpeg / .png  
* File size: ≤10MB, dimensions: min 300px, aspect ratio: 1:2.5 \~ 2.5:1  
* At least one of image or image\_tail must be provided; both cannot be empty

Support varies by model version and video mode. See [Capability Map](https://kling.ai/document-api/apiReference/model/videoModels) for details.

image\_tailstringOptional

Reference Image \- End frame control

* Supports image Base64 encoding or image URL (ensure accessibility)  
* Important: When using Base64, do NOT add any prefix like data:image/png;base64,. Submit only the raw Base64 string.  
* Supported image formats: .jpg / .jpeg / .png  
* File size: ≤10MB, dimensions: min 300px  
* At least one of image or image\_tail must be provided; both cannot be empty  
* image\_tail, dynamic\_masks/static\_mask, and camera\_control are mutually exclusive \- only one can be used at a time

Support varies by model version and video mode. See [Capability Map](https://kling.ai/document-api/apiReference/model/videoModels) for details.

multi\_shotbooleanOptionalDefault to false

Whether to generate multi-shot video

When true: the prompt parameter is invalid, and the first/end frame generation is not supported.

When false: the shot\_type and multi\_prompt parameters are invalid

shot\_typestringOptional

Storyboard method

Enum values：customizeintelligence

When multi\_shot is true, this parameter is required

promptstringOptional

Positive text prompt

💡

The Omni model can achieve various capabilities through Prompt with elements, images, videos, and other content:

* Specify elements/images/videos using \<\<\<\>\>\> format, e.g.: \<\<\<element\_1\>\>\>, \<\<\<image\_1\>\>\>, \<\<\<video\_1\>\>\>  
* For detailed capabilities, see: [KLING Omni Model User Guide](https://kling.ai/quickstart/klingai-video-o1-user-guide), [Kling VIDEO 3.0 Omni Model User Guide](https://kling.ai/quickstart/klingai-video-3-omni-model-user-guide)  
* Cannot exceed 2500 characters  
* When multi\_shot is false or shot\_type is intelligence, this parameter must not be empty.  
* Use \<\<\<voice\_1\>\>\> to specify voice, with the sequence matching the voice\_list parameter order  
* A video generation task can reference up to 2 voices; when specifying a voice, the sound parameter must be "on"  
* The simpler the syntax structure, the better. Example: The man\<\<\<voice\_1\>\>\> said: "Hello"  
* When voice\_list is not empty and prompt references voice ID, the task will be billed as "with specified voice"

Support varies by model version and video mode. See [Capability Map](https://kling.ai/document-api/apiReference/model/videoModels) for details.

multi\_promptarrayOptional

Information about each storyboard, such as prompts and duration

Define the shot sequence number, corresponding prompt word, and duration through the index, prompt, and duration parameters, where:

* Supports up to 6 storyboards, with a minimum of 1 storyboard.  
* The maximum length of the prompt for each storyboard 512 characters.  
* The duration of each storyboard should not exceed the total duration, but should not be less than 1\.  
* The sum of the durations of all storyboards equals the total duration of the current task.

Load with key:value format as follows:

When multi\_shot is true and shot\_type is customize, this parameter is required.

negative\_promptstringOptional

Negative text prompt

* Cannot exceed 2500 characters  
* It is recommended to supplement negative prompt via negative sentences within positive prompts

element\_listarrayOptional

Reference Element List, based on element ID from element library

* Supports up to 3 reference elements

The elements are categorized into video customization element (named as Video Character Elements) and image customization elements (named as Multi-Image Elements), each with distinct scopes of application. Please exercise caution in distinguishing between them. See [Kling Element Library User Guide](https://kling.ai/quickstart/klingai-element-library-3-user-guide).

* Load with key:value format as follows:

Support varies by model version and video mode. See [Capability Map](https://kling.ai/document-api/apiReference/model/videoModels) for details.

▾Hide child attributes

element\_idlongRequired

Element ID from element library

voice\_listarrayOptional

List of voices referenced when generating videos

* A video generation task can reference up to 2 voices  
* When voice\_list is not empty and prompt references voice ID, the task will be billed as "with specified voice"  
* voice\_id is returned through the voice customization API, or use system preset voices. See [Custom Voices API](https://kling.ai/document-api/apiReference/model/customVoices); NOT the voice\_id of Lip-Sync API  
* element\_list and voice\_list are mutually exclusive and cannot coexist

Example:

The support range for different model versions and video modes varies. For details, see [Capability Map](https://kling.ai/document-api/apiReference/model/videoModels)

soundstringOptionalDefault to off

Whether to generate sound when generating video

Enum values：onoff

The support range for different model versions and video modes varies. For details, see [Capability Map](https://kling.ai/document-api/apiReference/model/videoModels)

cfg\_scalefloatOptionalDefault to 0.5

Flexibility in video generation; higher value means lower model flexibility and stronger relevance to user prompt

* Value range: \[0, 1\]

kling-v2.x models do not support this parameter

modestringOptionalDefault to std

Video generation mode

Enum values：stdpro

* std: Standard Mode \- basic mode, cost-effective  
* pro: Professional Mode (High Quality) \- high performance mode, better video quality

Support varies by model version and video mode. See [Capability Map](https://kling.ai/document-api/apiReference/model/videoModels) for details.

static\_maskstringOptional

Static brush mask area (mask image created by user using motion brush)

The "Motion Brush" feature includes Dynamic Brush (dynamic\_masks) and Static Brush (static\_mask)

* Supports image Base64 encoding or image URL (same format requirements as image field)  
* Supported image formats: .jpg / .jpeg / .png  
* Aspect ratio must match the input image (image field), otherwise task will fail  
* Resolution of static\_mask and dynamic\_masks.mask must be identical, otherwise task will fail

Support varies by model version and video mode. See [Capability Map](https://kling.ai/document-api/apiReference/model/videoModels) for details.

dynamic\_masksarrayOptional

Dynamic brush configuration list

* Can configure multiple groups (up to 6), each containing "mask area" and "motion trajectory" sequence

Support varies by model version and video mode. See [Capability Map](https://kling.ai/document-api/apiReference/model/videoModels) for details.

▾Hide child attributes

maskstringRequired

Dynamic brush mask area (mask image created by user using motion brush)

* Supports image Base64 encoding or image URL (same format requirements as image field)  
* Supported image formats: .jpg / .jpeg / .png  
* Aspect ratio must match the input image (image field), otherwise task will fail  
* Resolution of static\_mask and dynamic\_masks.mask must be identical, otherwise task will fail

trajectoriesarrayRequired

Motion trajectory coordinate sequence

* For 5s video, trajectory length ≤77, coordinate count range: \[2, 77\]  
* Coordinate system uses bottom-left corner of image as origin

Note 1: More coordinate points \= more accurate trajectory. 2 points \= straight line between them

Note 2: Trajectory direction follows input order. First coordinate is start point, subsequent coordinates are connected sequentially

▾Hide child attributes

xintRequired

X coordinate of trajectory point (pixel coordinate with image bottom-left as origin)

yintRequired

Y coordinate of trajectory point (pixel coordinate with image bottom-left as origin)

camera\_controlobjectOptional

Camera movement control protocol (if not specified, model will intelligently match based on input text/images)

Support varies by model version and video mode. See [Capability Map](https://kling.ai/document-api/apiReference/model/videoModels) for details.

▾Hide child attributes

typestringRequired

Predefined camera movement type

Enum values：simpledown\_backforward\_upright\_turn\_forwardleft\_turn\_forward

* simple: Simple camera movement, can choose one of six options in "config"  
* down\_back: Camera descends and moves backward ➡️ Pan down and zoom out. config parameter not required  
* forward\_up: Camera moves forward and tilts up ➡️ Zoom in and pan up. config parameter not required  
* right\_turn\_forward: Rotate right then move forward ➡️ Right rotation advance. config parameter not required  
* left\_turn\_forward: Rotate left then move forward ➡️ Left rotation advance. config parameter not required

configobjectOptional

Contains 6 fields to specify camera movement in different directions

* Required when type is "simple"; leave empty for other types  
* Choose only one parameter to be non-zero; rest must be 0

▾Hide child attributes

horizontalfloatOptional

Horizontal movement \- camera translation along x-axis

* Value range: \[-10, 10\]. Negative \= left, Positive \= right

verticalfloatOptional

Vertical movement \- camera translation along y-axis

* Value range: \[-10, 10\]. Negative \= down, Positive \= up

panfloatOptional

Horizontal pan \- camera rotation around y-axis

* Value range: \[-10, 10\]. Negative \= rotate left, Positive \= rotate right

tiltfloatOptional

Vertical tilt \- camera rotation around x-axis

* Value range: \[-10, 10\]. Negative \= tilt down, Positive \= tilt up

rollfloatOptional

Roll \- camera rotation around z-axis

* Value range: \[-10, 10\]. Negative \= counterclockwise, Positive \= clockwise

zoomfloatOptional

Zoom \- controls camera focal length change, affects field of view

* Value range: \[-10, 10\]. Negative \= longer focal length (narrower FOV), Positive \= shorter focal length (wider FOV)

durationstringOptionalDefault to 5

Video duration in seconds

Enum values：3456789101112131415

Support varies by model version and video mode. See [Capability Map](https://kling.ai/document-api/apiReference/model/videoModels) for details.

watermark\_infoobjectOptional

Whether to generate watermarked results simultaneously

* Defined by the enabled parameter, format:  
* true: generate watermarked result, false: do not generate  
* Custom watermarks are not currently supported

callback\_urlstringOptional

Callback notification URL for task result. If configured, server will notify when task status changes.

* For specific message schema, see [Callback Protocol](https://kling.ai/document-api/apiReference/callbackProtocol)

external\_task\_idstringOptional

Customized Task ID

* Will not overwrite system-generated task ID, but supports querying task by this ID  
* Must be unique within a single user account

cURL

Copy

Collapse

`curl --location --request POST 'https://api-singapore.klingai.com/v1/videos/image2video' \`  
`--header 'Authorization: Bearer <token>' \`  
`--header 'Content-Type: application/json' \`  
`--data-raw '{`  
    `"model_name": "kling-v2-6",`  
    `"image": "https://p2-kling.klingai.com/kcdn/cdn-kcdn112452/kling-qa-test/multi-2.png",`  
    `"image_tail": "https://p2-kling.klingai.com/kcdn/cdn-kcdn112452/kling-qa-test/multi-1.png",`  
    `"prompt": "Camera zooms out, the girl smiles",`  
    `"negative_prompt": "",`  
    `"duration": "5",`  
    `"mode": "pro",`  
    `"sound": "off",`  
    `"callback_url": "",`  
    `"external_task_id": ""`

`}'`

**200**

Copy

Collapse

`{`  
  `"code": 0, // Error codes; Specific definitions can be found in "Error Code"`  
  `"message": "string", // Error information`  
  `"request_id": "string", // Request ID, generated by the system`  
  `"data": {`  
    `"task_id": "string", // Task ID, generated by the system`  
    `"task_info": { // Task creation parameters`  
      `"external_task_id": "string" // Customer-defined task ID`  
    `},`  
    `"task_status": "string", // Task status, Enum values: submitted, processing, succeed, failed`  
    `"created_at": 1722769557708, // Task creation time, Unix timestamp, unit ms`  
    `"updated_at": 1722769557708 // Task update time, Unix timestamp, unit ms`  
  `}`

`}`

## **Scenario invocation examples**

### **Image to video with multi-shot**

`curl --location 'https://xxx/v1/videos/image2video' \`  
`--header 'Authorization: Bearer xxx' \`  
`--header 'Content-Type: application/json' \`  
`--data '{`  
    `"model_name": "kling-v3",`  
    `"image": "xxx",`  
    `"prompt": "",`  
    `"multi_shot": "true",`  
    `"shot_type": "customize",`  
    `"multi_prompt": [`  
        `{`  
            `"index": 1,`  
            `"prompt": "Two friends talking under a streetlight at night.  Warm glow, casual poses, no dialogue.",`  
            `"duration": "2"`  
        `},`  
        `{`  
            `"index": 2,`  
            `"prompt": "A runner sprinting through a forest, leaves flying.  Low-angle shot, focus on movement.",`  
            `"duration": "3"`  
        `},`  
        `{`  
            `"index": 3,`  
            `"prompt": "A woman hugging a cat, smiling.  Soft sunlight, cozy home setting, emphasize warmth.",`  
            `"duration": "3"`  
        `},`  
        `{`  
            `"index": 4,`  
            `"prompt": "A door creaking open, shadowy hallway.  Dark tones, minimal details, eerie mood.",`  
            `"duration": "3"`  
        `},`  
        `{`  
            `"index": 5,`  
            `"prompt": "A man slipping on a banana peel, shocked expression.  Exaggerated pose, bright colors.",`  
            `"duration": "3"`  
        `},`  
        `{`  
            `"index": 6,`  
            `"prompt": "A sunset over mountains, small figure walking away.  Wide angle, peaceful atmosphere.",`  
            `"duration": "1"`  
        `}`  
    `],`  
    `"negative_prompt": "",`  
    `"duration": "15",`  
    `"mode": "pro",`  
    `"sound": "on",`  
    `"callback_url": "",`  
    `"external_task_id": ""`

`}'`

### **Image to video with element**

`curl --location 'https://api-singapore.klingai.com/v1/images/generations' \`  
`--header 'Authorization: Bearer xxx' \`  
`--header 'Content-Type: application/json' \`  
`--data '{`  
    `"model_name": "kling-v3",`  
    `"prompt": "Merge all the characters from the images into the <<<object_2>>> diagram",`  
    `"element_list": [`  
        `{`  
            `"element_id": "160"`  
        `},`  
        `{`  
            `"element_id": "161"`  
        `},`  
        `{`  
            `"element_id": "159"`  
        `}`  
    `],`  
    `"image": "xxx",`  
    `"resolution": "2k",`  
    `"n": "9",`  
    `"aspect_ratio": "3:2",`  
    `"external_task_id": "",`  
    `"callback_url": ""`

`}'`

`curl --location 'https://xxx/v1/videos/text2video' \`  
`--header 'Authorization: Bearer xxx' \`  
`--header 'Content-Type: application/json' \`  
`--data '{`  
    `"model_name": "kling-v3",`  
    `"prompt": "",`  
    `"multi_prompt": [`  
        `{`  
            `"index": 1,`  
            `"prompt": "Two friends talking under a streetlight at night.  Warm glow, casual poses, no dialogue.",`  
            `"duration": "2"`  
        `},`  
        `{`  
            `"index": 2,`  
            `"prompt": "A runner sprinting through a forest, leaves flying.  Low-angle shot, focus on movement.",`  
            `"duration": "3"`  
        `},`  
        `{`  
            `"index": 3,`  
            `"prompt": "A woman hugging a cat, smiling.  Soft sunlight, cozy home setting, emphasize warmth.",`  
            `"duration": "3"`  
        `},`  
        `{`  
            `"index": 4,`  
            `"prompt": "A door creaking open, shadowy hallway.  Dark tones, minimal details, eerie mood.",`  
            `"duration": "3"`  
        `},`  
        `{`  
            `"index": 5,`  
            `"prompt": "A man slipping on a banana peel, shocked expression.  Exaggerated pose, bright colors.",`  
            `"duration": "3"`  
        `},`  
        `{`  
            `"index": 6,`  
            `"prompt": "A sunset over mountains, small figure walking away.  Wide angle, peaceful atmosphere.",`  
            `"duration": "1"`  
        `}`  
    `],`  
    `"multi_shot": true,`  
    `"shot_type": "customize",`  
    `"duration": "15",`  
    `"mode": "pro",`  
    `"sound": "on",`  
    `"aspect_ratio": "9:16",`  
    `"callback_url": "",`  
    `"external_task_id": ""`

`}'`

### **Generate video with voice control**

`curl --location 'https://api-singapore.klingai.com/v1/videos/image2video/' \`  
`--header 'Authorization: Bearer {Replace your token}' \`  
`--header 'Content-Type: application/json; charset=utf-8' \`  
`--data '{`  
    `"model_name": "kling-v2-6",`  
    `"image": "Replace the URL of image",`  
    `"prompt": "<<<voice_1>>>Ask the people in the picture to say the following words, '\''Welcome everyone'\''",    //If a specific dialogue needs to be enclosed in quotation marks`  
    `"voice_list": [`  
        `{`  
            `"voice_id": "Replace the ID of voice"`  
        `}`  
    `],`  
    `"duration": "5",`  
    `"mode": "pro",`  
    `"sound": "on",`  
    `"callback_url": "",`  
    `"external_task_id": ""`

`}'`

---

## **Query Task (Single)**

GET/v1/videos/image2video/{id}

### **Request Header**

Content-TypestringRequiredDefault to application/json

Data Exchange Format

AuthorizationstringRequired

Authentication information, refer to API authentication

### **Path Parameters**

task\_idstringOptional

Task ID for image to video

* Request path parameter, fill value directly in request path  
* Choose one between task\_id and external\_task\_id for querying

external\_task\_idstringOptional

Customized Task ID for image to video

* The external\_task\_id provided when creating the task  
* Choose one between task\_id and external\_task\_id for querying

cURL

Copy

Collapse

`curl --request GET \`  
  `--url https://api-singapore.klingai.com/v1/videos/image2video/{task_id} \`

  `--header 'Authorization: Bearer <token>'`

**200**

Copy

Collapse

`{`  
  `"code": 0, // Error codes; Specific definitions can be found in "Error Code"`  
  `"message": "string", // Error information`  
  `"request_id": "string", // Request ID, generated by the system, is used to track requests and troubleshoot problems`  
  `"data": {`  
    `"task_id": "string", // Task ID, generated by the system`  
    `"task_status": "string", // Task status, Enum values: submitted, processing, succeed, failed`  
    `"task_status_msg": "string", // Task status information, displaying the failure reason when the task fails (such as triggering the content risk control of the platform, etc.)`  
    `"watermark_info": {`  
      `"enabled": boolean`  
    `},`  
    `"task_result": {`  
      `"videos": [`  
        `{`  
          `"id": "string", // Generated video ID; globally unique`  
          `"url": "string", // URL for generating videos (To ensure information security, generated images/videos will be cleared after 30 days. Please make sure to save them promptly.)`  
          `"watermark_url": "string", // Watermarked video download URL, anti-leech format`  
          `"duration": "string" // Total video duration, unit: s`  
        `}`  
      `]`  
    `},`  
    `"task_info": { // Task creation parameters`  
      `"external_task_id": "string" // Customer-defined task ID`  
    `},`  
    `"final_unit_deduction": "string", // The deduction units of task`  
    `"created_at": 1722769557708, // Task creation time, Unix timestamp, unit: ms`  
    `"updated_at": 1722769557708 // Task update time, Unix timestamp, unit: ms`  
  `}`

`}`

---

## **Query Task (List)**

GET/v1/videos/image2video

### **Request Header**

Content-TypestringRequiredDefault to application/json

Data Exchange Format

AuthorizationstringRequired

Authentication information, refer to API authentication

### **Query Parameters**

pageNumintOptionalDefault to 1

Page number

* Value range: \[1, 1000\]

pageSizeintOptionalDefault to 30

Data volume per page

* Value range: \[1, 500\]

cURL

Copy

Collapse

`curl --request GET \`  
  `--url 'https://api-singapore.klingai.com/v1/videos/image2video?pageNum=1&pageSize=30' \`

  `--header 'Authorization: Bearer <token>'`

**200**

Copy

Collapse

`{`  
  `"code": 0, // Error codes; Specific definitions can be found in Error codes`  
  `"message": "string", // Error information`  
  `"request_id": "string", // Request ID, generated by the system, to track requests and troubleshoot problems`  
  `"data": [`  
    `{`  
      `"task_id": "string", // Task ID, generated by the system`  
      `"task_status": "string", // Task status, Enum values: submitted, processing, succeed, failed`  
      `"task_status_msg": "string", // Task status information, displaying the failure reason when the task fails (such as triggering the content risk control of the platform, etc.)`  
      `"task_info": { // Task creation parameters`  
        `"external_task_id": "string" // Customer-defined task ID`  
      `},`  
      `"task_result": {`  
        `"videos": [`  
          `{`  
            `"id": "string", // Generated video ID; globally unique`  
            `"url": "string", // URL for generating videos (To ensure information security, generated images/videos will be cleared after 30 days. Please make sure to save them promptly.)`  
            `"watermark_url": "string", // Watermarked video download URL, anti-leech format`  
            `"duration": "string" // Total video duration, unit: s (seconds)`  
          `}`  
        `]`  
      `},`  
      `"watermark_info": {`  
        `"enabled": boolean`  
      `},`  
      `"final_unit_deduction": "string", // The deduction units of task`  
      `"created_at": 1722769557708, // Task creation time, Unix timestamp, unit: ms`  
      `"updated_at": 1722769557708 // Task update time, Unix timestamp, unit: ms`  
    `}`  
  `]`

`}`

Previous chapter：Text to Video

Next chapter：Reference to Video

Create Task

Scenario invocation examples

Query Task (Single)

Query Task (List)

# Lip sync

Search

* Get Started  
  * [Overview](https://kling.ai/document-api/quickStart%2FproductIntroduction%2Foverview)  
  * [Quick Start](https://kling.ai/document-api/quickStart%2FuserManual)  
  * [Changelog](https://kling.ai/document-api/apiReference%2FupdateNotice)  
* API Reference  
  * [General Info](https://kling.ai/document-api/apiReference%2FcommonInfo)  
  * [Rate Limits](https://kling.ai/document-api/apiReference%2FrateLimits)  
  * [Callback Schema](https://kling.ai/document-api/apiReference%2FcallbackProtocol)  
  * Video Generation  
    * [Models](https://kling.ai/document-api/apiReference%2Fmodel%2FvideoModels)  
    * [Video Omni](https://kling.ai/document-api/apiReference%2Fmodel%2FOmniVideo)  
    * [Text to Video](https://kling.ai/document-api/apiReference%2Fmodel%2FtextToVideo)  
    * [Image to Video](https://kling.ai/document-api/apiReference%2Fmodel%2FimageToVideo)  
    * [Reference to Video](https://kling.ai/document-api/apiReference%2Fmodel%2FmultiImageToVideo)  
    * [Motion Control](https://kling.ai/document-api/apiReference%2Fmodel%2FmotionControl)  
    * [Multi-elements to video](https://kling.ai/document-api/apiReference%2Fmodel%2FmultiElements)  
    * [Extend Video](https://kling.ai/document-api/apiReference%2Fmodel%2FvideoExtension)  
    * [Lip Sync](https://kling.ai/document-api/apiReference%2Fmodel%2FlipSync)  
    * [Avatar](https://kling.ai/document-api/apiReference%2Fmodel%2Favatar)  
    * [Text to Audio](https://kling.ai/document-api/apiReference%2Fmodel%2FtextToAudio)  
    * [Video to Audio](https://kling.ai/document-api/apiReference%2Fmodel%2FvideoToAudio)  
    * [Text to Speech](https://kling.ai/document-api/apiReference%2Fmodel%2FTTS)  
    * [Voice Clone](https://kling.ai/document-api/apiReference%2Fmodel%2FcustomVoices)  
    * [Image Recognize](https://kling.ai/document-api/apiReference%2Fmodel%2FimageRecognize)  
    * [Element](https://kling.ai/document-api/apiReference%2Fmodel%2Felement)  
  * Effects  
    * [Effect TemplatesNEW](https://kling.ai/document-api/quickStart%2FproductIntroduction%2FeffectsCenter)  
    * [Video Effects](https://kling.ai/document-api/apiReference%2Fmodel%2FvideoEffects)  
  * Image Generation  
    * [Models](https://kling.ai/document-api/apiReference%2Fmodel%2FimageModels)  
    * [Image Omni](https://kling.ai/document-api/apiReference%2Fmodel%2FOmniImage)  
    * [Image Generation](https://kling.ai/document-api/apiReference%2Fmodel%2FimageGeneration)  
    * [Reference to Image](https://kling.ai/document-api/apiReference%2Fmodel%2FmultiImageToImage)  
    * [Extend Image](https://kling.ai/document-api/apiReference%2Fmodel%2FimageExpansion)  
    * [AI Multi-Shot](https://kling.ai/document-api/apiReference%2Fmodel%2FaiMultiShot)  
    * [Virtual Try-On](https://kling.ai/document-api/apiReference%2Fmodel%2FvirtualTryOn)  
  * Others  
    * [Query user info](https://kling.ai/document-api/apiReference%2FaccountInfoInquiry)  
* Pricing  
  * [Billing Info](https://kling.ai/document-api/productBilling%2FbillingMethod)  
  * [Prepaid Resource Packs](https://kling.ai/document-api/productBilling%2FprePaidResourcePackage)  
* Protocols  
  * [Privacy Policy of API Service](https://kling.ai/document-api/protocols%2FprivacyPolicy)  
  * [Terms of API Service](https://kling.ai/document-api/protocols%2FpaidServiceProtocol)  
  * [API Service Level Agreement](https://kling.ai/document-api/protocols%2FpaidLevelProtocol)

# **Lip-Sync**

---

## **Identify Face**

POST/v1/videos/identify-face

Identify faces in the video for lip-sync processing.

### **Request Header**

Content-TypestringRequiredDefault to application/json

Data Exchange Format

AuthorizationstringRequired

Authentication information, refer to API authentication

### **Request Body**

video\_idstringOptional

The ID of the video generated by Kling AI

* Used to specify the video and determine whether it can be used for lip-sync services.  
* This parameter and 'video\_url' are mutually exclusive—only one can be filled, and neither can be left empty.  
* Only supports videos generated within the last 30 days with a duration of no more than 60 seconds.

video\_urlstringOptional

The URL of the video

* Used to specify the video and determine whether it can be used for lip-sync services.  
* This parameter and 'video\_id' are mutually exclusive—only one can be filled, and neither can be left empty.  
* Supported video formats: .mp4/.mov, file size ≤100MB, duration 2s–60s, resolution 720p or 1080p, with both width and height between 512px–2160px. If validation fails, an error code will be returned.  
* The system checks video content—if issues are detected, an error code will be returned.

cURL

Copy

Collapse

`curl --request POST \`  
  `--url https://api-singapore.klingai.com/v1/videos/identify-face \`  
  `--header 'Authorization: Bearer <token>' \`  
  `--header 'Content-Type: application/json' \`  
  `--data '{`  
    `"video_url": "https://p1-kling.klingai.com/kcdn/cdn-kcdn112452/kling-qa-test/kling20260206mp4.mp4",`  
    `"video_id": ""`

  `}'`

**200**

Copy

Collapse

`{`  
  `"code": 0, // Error codes; Specific definitions can be found in "Error Code"`  
  `"message": "string", // Error information`  
  `"request_id": "string", // Request ID, generated by the system, used to track requests and troubleshoot problems`  
  `"data": {`  
    `"session_id": "id", // Session ID`  
    `"final_unit_deduction": "string", // The deduction units of task`  
    `"face_data": [ //Face data list`  
      `{`  
        `"face_id": "string", // Face ID`  
        `"face_image": "url", // Face image URL`  
        `"start_time": 0, // Face appearance start time, unit: ms`  
        `"end_time": 5200 //Face appearance end time, unit: ms`  
      `}`  
    `]`  
  `}`

`}`

---

## **Create Task**

POST/v1/videos/advanced-lip-sync

### **Request Header**

Content-TypestringRequiredDefault to application/json

Data Exchange Format

AuthorizationstringRequired

Authentication information, refer to API authentication

### **Request Body**

session\_idstringRequired

Session ID generated during the identify face API. It remains unchanged during the selection/editing process.

face\_choosearrayRequired

Specified Face for Lip-Sync

* Includes Face ID, lip movement reference data, etc.  
* Currently only supports one person lip-sync.

▾Hide child attributes

face\_idstringRequired

Face ID

* Returned by the facial recognition interface.

audio\_idstringOptional

Sound ID Generated via TTS API

* Only supports audio generated within the last 30 days with a duration of no less than 2 seconds and no more than 60 seconds.  
* Either audio\_id or sound\_file must be provided (mutually exclusive; cannot be empty or both populated).

sound\_filestringOptional

Sound File

* Supports Base64-encoded audio or accessible audio URL.  
* Accepted formats: .mp3/.wav/.m4a/.aac (max 5MB). Format mismatches or oversized files will return error codes.  
* Only supports audio with a duration of no less than 2 seconds and no more than 60 seconds.  
* Either audio\_id or sound\_file must be provided (mutually exclusive; cannot be empty or both populated).  
* The system will verify the audio content and return error codes if there are any problems.

sound\_start\_timelongRequired

Time point to start cropping sound

* Based on the original sound start time, the start time is 0'0", units: ms  
* The sound before the starting point will be cropped, and the cropped sound must not be shorter than 2 seconds.

sound\_end\_timelongRequired

Time point to stop cropping sound

* Based on the original sound start time, the start time is 0'0", units: ms  
* The sound after the end point will be cropped, and the cropped sound must not be shorter than 2 seconds.  
* The end point time shouldn't be later than the total duration of the original sound.

sound\_insert\_timelongRequired

The time for inserting cropped sound

* Based on the original video start time, the start time is 0'0", units: ms  
* The time range for inserting sound should overlap with the face's lip-sync time interval for at least 2 seconds.  
* The start time for inserting sound must not be earlier than the start time of the video, and the end time for inserting sound must not be later than the end time of the video.

sound\_volumefloatOptionalDefault to 1

Volume Controls (higher values \= louder)

* Value range: \[0, 2\]

original\_audio\_volumefloatOptionalDefault to 1

Original video volume (higher values \= louder)

* Value range: \[0, 2\]  
* No effect if source video is silent.

watermark\_infoobjectOptional

Whether to generate watermarked results simultaneously

* Defined by the enabled parameter, format:  
* true: generate watermarked result, false: do not generate  
* Custom watermarks are not currently supported

external\_task\_idstringOptional

Custom Task ID

* User-defined task ID. It will not override the system-generated task ID, but supports querying tasks by this ID.  
* Please note that uniqueness must be ensured for each user.

callback\_urlstringOptional

The callback notification address for the result of this task. If configured, the server will actively notify when the task status changes.

* For specific message schema, see [Callback Protocol](https://kling.ai/document-api/apiReference/callbackProtocol)

cURL

Copy

Collapse

`curl --request POST \`  
  `--url https://api-singapore.klingai.com/v1/videos/advanced-lip-sync \`  
  `--header 'Authorization: Bearer <token>' \`  
  `--header 'Content-Type: application/json' \`  
  `--data '{`  
    `"session_id": "850508686686064678",`  
    `"face_choose": [`  
      `{`  
        `"face_id": "0",`  
        `"sound_file": "https://p1-kling.klingai.com/kcdn/cdn-kcdn112452/kling-qa-test/go-to-world.mp3",`  
        `"sound_insert_time": 1000,`  
        `"sound_start_time": 0,`  
        `"sound_end_time": 3000,`  
        `"sound_volume": 2,`  
        `"original_audio_volume": 2`  
      `}`  
    `],`  
    `"external_task_id": "",`  
    `"callback_url": ""`

  `}'`

**200**

Copy

Collapse

`{`  
  `"code": 0, // Error codes; Specific definitions can be found in "Error Code"`  
  `"message": "string", // Error information`  
  `"request_id": "string", // Request ID, generated by the system, used to track requests and troubleshoot problems`  
  `"data": {`  
    `"task_id": "string", // Task ID, generated by the system`  
    `"task_info": { //Task creation parameters`  
      `"external_task_id": "string" //User-defined task ID`  
    `},`  
    `"task_status": "string", // Task status, Enum values: submitted, processing, succeed, failed`  
    `"created_at": 1722769557708, // Task creation time, Unix timestamp, unit: ms`  
    `"updated_at": 1722769557708 //Task update time, Unix timestamp, unit: ms`  
  `}`

`}`

---

## **Query Task (Single)**

GET/v1/videos/advanced-lip-sync/{id}

### **Request Header**

Content-TypestringRequiredDefault to application/json

Data Exchange Format

AuthorizationstringRequired

Authentication information, refer to API authentication

### **Path Parameters**

task\_idstringOptional

Task ID for Video Generation \- Lip-Sync. Fill the value directly in the request path.

cURL

Copy

Collapse

`curl --request GET \`  
  `--url https://api-singapore.klingai.com/v1/videos/advanced-lip-sync/{task_id} \`

  `--header 'Authorization: Bearer <token>'`

**200**

Copy

Collapse

`{`  
  `"code": 0, // Error codes; Specific definitions can be found in "Error Code"`  
  `"message": "string", // Error information`  
  `"request_id": "string", // Request ID, generated by the system, used to track requests and troubleshoot problems`  
  `"data": {`  
    `"task_id": "string", // Task ID, generated by the system`  
    `"task_status": "string", // Task status, Enum values: submitted, processing, succeed, failed`  
    `"task_status_msg": "string", // Task status message, displaying the failure reason when the task fails (such as triggering the content risk control of the platform, etc.)`  
    `"task_info": { //Task creation parameters`  
      `"parent_video": { //Original video information`  
        `"id": "string", // Original video ID`  
        `"url": "string", // Original video URL`  
        `"duration": "string" //Original video duration, unit: s`  
      `}`  
    `},`  
    `"task_result": { //Task result`  
      `"videos": [ //Generated video list`  
        `{`  
          `"id": "string", // Generated video ID; globally unique`  
          `"url": "string", // URL for generating videos (Please note that for security purposes, generated images/videos will be deleted after 30 days. Please save them promptly.)`  
          `"watermark_url": "string", // Watermarked video download URL, anti-hotlinking format`  
          `"duration": "string" //Total video duration, unit: s`  
        `}`  
      `]`  
    `},`  
    `"watermark_info": {`  
      `"enabled": boolean //Whether watermark is enabled`  
    `},`  
    `"final_unit_deduction": "string", // The deduction units of task`  
    `"created_at": 1722769557708, // Task creation time, Unix timestamp, unit: ms`  
    `"updated_at": 1722769557708 //Task update time, Unix timestamp, unit: ms`  
  `}`

`}`

---

## **Query Task (List)**

GET/v1/videos/advanced-lip-sync

### **Request Header**

Content-TypestringRequiredDefault to application/json

Data Exchange Format

AuthorizationstringRequired

Authentication information, refer to API authentication

### **Query Parameters**

pageNumintOptionalDefault to 1

Page number

* Value range: \[1, 1000\]

pageSizeintOptionalDefault to 30

Number of items per page

* Value range: \[1, 500\]

cURL

Copy

Collapse

`curl --request GET \`  
  `--url 'https://api-singapore.klingai.com/v1/videos/advanced-lip-sync?pageNum=1&pageSize=30' \`

  `--header 'Authorization: Bearer <token>'`

**200**

Copy

Collapse

`{`  
  `"code": 0, // Error codes; Specific definitions can be found in "Error Code"`  
  `"message": "string", // Error information`  
  `"request_id": "string", // Request ID, generated by the system, used to track requests and troubleshoot problems`  
  `"data": [`  
    `{`  
      `"task_id": "string", // Task ID, generated by the system`  
      `"task_status": "string", // Task status, Enum values: submitted, processing, succeed, failed`  
      `"task_status_msg": "string", // Task status message, displaying the failure reason when the task fails (such as triggering the content risk control of the platform, etc.)`  
      `"task_info": { //Task creation parameters`  
        `"parent_video": { //Original video information`  
          `"id": "string", // Original video ID`  
          `"url": "string", // Original video URL`  
          `"duration": "string" //Original video duration, unit: s`  
        `}`  
      `},`  
      `"task_result": { //Task result`  
        `"videos": [ //Generated video list`  
          `{`  
            `"id": "string", // Generated video ID; globally unique`  
            `"url": "string", // URL for generating videos (Please note that for security purposes, generated images/videos will be deleted after 30 days. Please save them promptly.)`  
            `"watermark_url": "string", // Watermarked video download URL, anti-hotlinking format`  
            `"duration": "string" //Total video duration, unit: s`  
          `}`  
        `]`  
      `},`  
      `"watermark_info": {`  
        `"enabled": boolean //Whether watermark is enabled`  
      `},`  
      `"final_unit_deduction": "string", // The deduction units of task`  
      `"created_at": 1722769557708, // Task creation time, Unix timestamp, unit: ms`  
      `"updated_at": 1722769557708 //Task update time, Unix timestamp, unit: ms`  
    `}`  
  `]`

`}`

Previous chapter：Extend Video

Next chapter：Avatar

Identify Face

Create Task

Query Task (Single)

Query Task (List)

# JWT

Search

* Get Started  
  * [Overview](https://kling.ai/document-api/quickStart%2FproductIntroduction%2Foverview)  
  * [Quick Start](https://kling.ai/document-api/quickStart%2FuserManual)  
  * [Changelog](https://kling.ai/document-api/apiReference%2FupdateNotice)  
* API Reference  
  * [General Info](https://kling.ai/document-api/apiReference%2FcommonInfo)  
  * [Rate Limits](https://kling.ai/document-api/apiReference%2FrateLimits)  
  * [Callback Schema](https://kling.ai/document-api/apiReference%2FcallbackProtocol)  
  * Video Generation  
    * [Models](https://kling.ai/document-api/apiReference%2Fmodel%2FvideoModels)  
    * [Video Omni](https://kling.ai/document-api/apiReference%2Fmodel%2FOmniVideo)  
    * [Text to Video](https://kling.ai/document-api/apiReference%2Fmodel%2FtextToVideo)  
    * [Image to Video](https://kling.ai/document-api/apiReference%2Fmodel%2FimageToVideo)  
    * [Reference to Video](https://kling.ai/document-api/apiReference%2Fmodel%2FmultiImageToVideo)  
    * [Motion Control](https://kling.ai/document-api/apiReference%2Fmodel%2FmotionControl)  
    * [Multi-elements to video](https://kling.ai/document-api/apiReference%2Fmodel%2FmultiElements)  
    * [Extend Video](https://kling.ai/document-api/apiReference%2Fmodel%2FvideoExtension)  
    * [Lip Sync](https://kling.ai/document-api/apiReference%2Fmodel%2FlipSync)  
    * [Avatar](https://kling.ai/document-api/apiReference%2Fmodel%2Favatar)  
    * [Text to Audio](https://kling.ai/document-api/apiReference%2Fmodel%2FtextToAudio)  
    * [Video to Audio](https://kling.ai/document-api/apiReference%2Fmodel%2FvideoToAudio)  
    * [Text to Speech](https://kling.ai/document-api/apiReference%2Fmodel%2FTTS)  
    * [Voice Clone](https://kling.ai/document-api/apiReference%2Fmodel%2FcustomVoices)  
    * [Image Recognize](https://kling.ai/document-api/apiReference%2Fmodel%2FimageRecognize)  
    * [Element](https://kling.ai/document-api/apiReference%2Fmodel%2Felement)  
  * Effects  
    * [Effect TemplatesNEW](https://kling.ai/document-api/quickStart%2FproductIntroduction%2FeffectsCenter)  
    * [Video Effects](https://kling.ai/document-api/apiReference%2Fmodel%2FvideoEffects)  
  * Image Generation  
    * [Models](https://kling.ai/document-api/apiReference%2Fmodel%2FimageModels)  
    * [Image Omni](https://kling.ai/document-api/apiReference%2Fmodel%2FOmniImage)  
    * [Image Generation](https://kling.ai/document-api/apiReference%2Fmodel%2FimageGeneration)  
    * [Reference to Image](https://kling.ai/document-api/apiReference%2Fmodel%2FmultiImageToImage)  
    * [Extend Image](https://kling.ai/document-api/apiReference%2Fmodel%2FimageExpansion)  
    * [AI Multi-Shot](https://kling.ai/document-api/apiReference%2Fmodel%2FaiMultiShot)  
    * [Virtual Try-On](https://kling.ai/document-api/apiReference%2Fmodel%2FvirtualTryOn)  
  * Others  
    * [Query user info](https://kling.ai/document-api/apiReference%2FaccountInfoInquiry)  
* Pricing  
  * [Billing Info](https://kling.ai/document-api/productBilling%2FbillingMethod)  
  * [Prepaid Resource Packs](https://kling.ai/document-api/productBilling%2FprePaidResourcePackage)  
* Protocols  
  * [Privacy Policy of API Service](https://kling.ai/document-api/protocols%2FprivacyPolicy)  
  * [Terms of API Service](https://kling.ai/document-api/protocols%2FpaidServiceProtocol)  
  * [API Service Level Agreement](https://kling.ai/document-api/protocols%2FpaidLevelProtocol)

# **General Information**

---

## **API Domain**

`https://api-singapore.klingai.com`

💡

Notice: The API endpoint for the new system has been updated from [https://api.klingai.com](https://api.klingai.com/) to [https://api-singapore.klingai.com](https://api-singapore.klingai.com/). This API is suitable for users whose servers are located outside of China.

## **API Authentication**

* Step-1：Obtain AccessKey \+ SecretKey  
* Step-2：Every time you request the API, you need to generate an API Token according to the fixed encryption method; put Authorization \= Bearer \<API Token\> in the Request Header  
  * Encryption Method：Follow JWT（Json Web Token, RFC 7519）standard  
  * JWT consists of three parts：Header、Payload、Signature

Python

Java

Copy

Collapse

`import time`  
`import jwt`

`ak = "" # fill access key`  
`sk = "" # fill secret key`

`def encode_jwt_token(ak, sk):`  
    `headers = {`  
        `"alg": "HS256",`  
        `"typ": "JWT"`  
    `}`  
    `payload = {`  
        `"iss": ak,`  
        `"exp": int(time.time()) + 1800, # The valid time, in this example, represents the current time+1800s(30min)`  
        `"nbf": int(time.time()) - 5 # The time when it starts to take effect, in this example, represents the current time -5s`  
    `}`  
    `token = jwt.encode(payload, sk, headers=headers)`  
    `return token`

`authorization = encode_jwt_token(ak, sk)`

`print(authorization) # Printing the generated API_TOKEN`

* Step-3: Use the API Token generated in Step 2 to assemble the Authorization and include it in the Request Header.  
  * Assembly format: Authorization \= “Bearer XXX”, where XXX is the API Token generated in Step 2\.  
  * Note: There should be a space between Bearer and XXX.

## **Error Code**

| HTTP Status Code | Service Code | Definition of Service Code | Explaination of Service Code | Suggested Solutions |
| :---: | :---: | :---: | :---: | :---: |
| 200 | 0 | Request successful | \- | \- |
| 401 | 1000 | Authentication failed | Authentication failed | Check if the Authorization is correct |
| 401 | 1001 | Authentication failed | Authorization is empty | Fill in the correct Authorization in the Request Header |
| 401 | 1002 | Authentication failed | Authorization is invalid | Fill in the correct Authorization in the Request Header |
| 401 | 1003 | Authentication failed | Authorization is not yet valid | Check the start effective time of the token, wait for it to take effect or reissue |
| 401 | 1004 | Authentication failed | Authorization has expired | Check the validity period of the token and reissue it |
| 429 | 1100 | Account exception | Account exception | Verifying account configuration information |
| 429 | 1101 | Account exception | Account in arrears (postpaid scenario) | Recharge the account to ensure sufficient balance |
| 429 | 1102 | Account exception | Resource pack depleted or expired (prepaid scenario) | Purchase additional resource packages, or activate the post-payment service (if available) |
| 403 | 1103 | Account exception | Unauthorized access to requested resource, such as API/model | Verifying account permissions |
| 400 | 1200 | Invalid request parameters | Invalid request parameters | Check whether the request parameters are correct |
| 400 | 1201 | Invalid request parameters | Invalid parameters, such as incorrect key or illegal value | Refer to the specific information in the message field of the returned body and modify the request parameters |
| 404 | 1202 | Invalid request parameters | The requested method is invalid | Review the API documentation and use the correct request method |
| 404 | 1203 | Invalid request parameters | The requested resource does not exist, such as the model | Refer to the specific information in the message field of the returned body and modify the request parameters |
| 400 | 1300 | Trigger strategy | Trigger strategy of the platform | Check if any platform policies have been triggered |
| 400 | 1301 | Trigger strategy | Trigger the content security policy of the platform | Check the input content, modify it, and resend the request |
| 429 | 1302 | Trigger strategy | The API request is too fast, exceeding the platform’s rate limit | Reduce the request frequency, try again later, or contact customer service to increase the limit |
| 429 | 1303 | Trigger strategy | Concurrency or QPS exceeds the prepaid resource package limit | Reduce the request frequency, try again later, or contact customer service to increase the limit |
| 429 | 1304 | Trigger strategy | Trigger the platform’s IP whitelisting policy | Contact customer service |
| 500 | 5000 | Internal error | Server internal error | Try again later, or contact customer service |
| 503 | 5001 | Internal error | Server temporarily unavailable, usually due to maintenance | Try again later, or contact customer service |
| 504 | 5002 | Internal error | Server internal timeout, usually due to a backlog | Try again later, or contact customer service |

Previous chapter：Changelog

Next chapter：Rate Limits

API Domain

API Authentication

Error Code

