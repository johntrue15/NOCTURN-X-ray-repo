# Tooling to Build

## 30,000ft. Focus
### END to END Morphosource record updater which summarizes metadata & slices to text


### END to END Raspi .iso file flash to Github Release from .pca file write

### 
---
---

## 10,000ft. Prioritize
#### ISO file as package
> Raspi development for .pca file MVP --> Github release
#### Selenium 2D vs. 3D Check
> selenium_test.yml needs to become selenium_2D_test.yml (slice pages) & selenium_3D_test.yml (volume pages)
#### Automate johntrue15.github.io blog posts from morphosource data
> summarize weekly posts from 2024 retroactively
> summarize weekly posts from 2025 live
#### Enable easy to use branch/raspi onboarding
> create github-pages 

---

##  500ft. Selenium Coding Dev Workflow

#### `selenium_test.yml`
- **CURRENTLY**  
  11-minute working demo of a 2D screenshot on **`workflow_dispatch:`**  
- **IF**  
  This code works, we push it to `selenium_screenshot_new.yml`.
- **TODO**
  create selenium_2D_test.yml`          (slice pages)
  create selenium_3D_test.yml`          (volume pages)
  create selenium_test_slices.yml`       (control slice button)
  create selenium_test_origin.yml`       (press origin button)
  create selenium_test_zoom.yml`         (control zoom button)
  create selenium_test_view_mode.yml`   (control slice/mesh view)
  create selenium_test_move_mesh.yml`   (move mesh view)

---

#### `selenium_screenshot_new.yml`
- **CURRENTLY**  
  Working with filename update on **completion**.  
- **IF**  
  This code works, we configure it to be automated in **`selenium_screenshot.yml`**.

---

#### `selenium_screenshot.yml`
- **CURRENTLY**  
  Working with `fullscreen.png` **completion**.  
- **IF**  
  This code works, we configure it to be automated in **`move_slices.yml`**.

---

#### `move_slices.yml`
- **CURRENTLY**  
  Working on an 18-minute example of exporting 100 slices from  
  [MorphoSource Media #000695203](https://www.morphosource.org/concern/media/000695203?locale=en)  
- **IF**  
  This code works, we configure it to be automated in **`automated_slices_to_text.yml`**.

---

#### `automated_slices_to_text.yml`
- **CURRENTLY**  
  Working on a 19-minute example, but the OpenAI prompt needs fixing.  
- **IF**  
  This code works, we configure it to work on **completion** from `CT_to_text`.  
- **TODO**  
  Add in Jupyter Notebook fixes from cursor → **Test Token Limit**.
