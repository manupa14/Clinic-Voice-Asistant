

---

### PyCharm quick run

1) In the Project pane, right-click **`src/` → Mark Directory As → Sources Root** (it will turn blue).
2) Go to **Run › Edit Configurations…** and create a **Python** configuration:
   - **Module name:** `app.ui_gradio`
   - **Working directory:** project root (folder containing `src/`)
   - Interpreter: your `.venv`
3) Copy `.env.example` → `.env` and fill keys. Run.

**CLI alternatives:**

- Without install (set PYTHONPATH in one shot):
  ```bash
  PYTHONPATH=src python -m app.ui_gradio
  ```

- With editable install (cleaner imports):
  ```bash
  pip install -e .
  python -m app.ui_gradio
  ```
