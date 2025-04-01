from nicegui import ui

buttons = {}


def load_test_tab(tab: str):
    with ui.tab_panel(tab).classes('w-full'):
        with ui.row().classes('items-center justify-center w-full h-full'):
            ui.spinner().classes('w-full h-full')
        # ui.label('Test Tab').classes('text-bold text-h6')
        # buttons["Test Button"] = ui.button('Test Button', on_click=lambda: button_lambda())


def button_lambda():
    ui.notify('Test Button Clicked!')
    show_button_data()


def show_button_data():
    for button_name, button in buttons.items():
        ui.label(f"{button_name} clicked {button.clicked} times.")
