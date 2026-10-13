"""Central semantic color system for every dashboard theme and color mode."""

from __future__ import annotations

from typing import Dict, Mapping


Theme = Dict[str, str]
DEFAULT_CUSTOM_BIBLE_COLOR = "#1E90FF"


# Native Settings follows Anki's application appearance only. Dashboard theme
# selection never recolors the editor itself.
SETTINGS_COLOR_TOKENS: Mapping[str, Mapping[str, str]] = {
    "dark": {
        "ui_bg": "#101215",
        "ui_sidebar": "#101215",
        "ui_surface": "#191C21",
        "ui_surface_raised": "#22262D",
        "ui_surface_hover": "#202C37",
        "ui_border": "#353A43",
        "ui_border_strong": "#3A4C5E",
        "ui_text_primary": "#F2F3F5",
        "ui_text_secondary": "#ACB3BF",
        "ui_text_muted": "#ACB3BF",
        "ui_accent": "#8CB6FF",
        "ui_accent_soft": "#1B3354",
        "ui_accent_hover": "#B1C9DD",
        "ui_accent_pressed": "#8AA7BF",
        "ui_accent_ink": "#081727",
        "ui_warning": "#E2BD57",
        "ui_success": "#63D49A",
        "ui_danger": "#F47F8D",
        "ui_overlay": "rgba(0, 0, 0, 153)"
    },
    "light": {
        "ui_bg": "#F4F5F7",
        "ui_sidebar": "#F4F5F7",
        "ui_surface": "#FFFFFF",
        "ui_surface_raised": "#F5F6F8",
        "ui_surface_hover": "#EDF1F4",
        "ui_border": "#DDDFE4",
        "ui_border_strong": "#AAB8C5",
        "ui_text_primary": "#20242B",
        "ui_text_secondary": "#5C6470",
        "ui_text_muted": "#5C6470",
        "ui_accent": "#275ED6",
        "ui_accent_soft": "#EAF1FF",
        "ui_accent_hover": "#506D87",
        "ui_accent_pressed": "#445F78",
        "ui_accent_ink": "#FFFFFF",
        "ui_warning": "#8A6815",
        "ui_success": "#2F7D50",
        "ui_danger": "#B1374A",
        "ui_overlay": "rgba(0, 0, 0, 140)"
    }
}


def _channels(value: str) -> list[int]:
    raw = value.lstrip("#")
    if len(raw) != 6:
        raise ValueError("theme colors must use six-digit hexadecimal notation")
    return [int(raw[index:index + 2], 16) for index in (0, 2, 4)]


def composite_color(foreground: str, background: str, opacity: float) -> str:
    """Return the opaque sRGB result of drawing foreground over background."""

    values = [
        round(opacity * front + (1 - opacity) * back)
        for front, back in zip(_channels(foreground), _channels(background))
    ]
    return "#{:02X}{:02X}{:02X}".format(*values)


def rgba_color(value: str, opacity: float) -> str:
    """Return a centralized CSS color for a translucent component surface."""

    channel_values = _channels(value)
    return "rgba({}, {}, {}, {:.2f})".format(
        *channel_values,
        max(0.0, min(1.0, opacity)),
    )


def _luminance(value: str) -> float:
    channels = [item / 255 for item in _channels(value)]
    linear = [
        item / 12.92 if item <= .04045 else ((item + .055) / 1.055) ** 2.4
        for item in channels
    ]
    return .2126 * linear[0] + .7152 * linear[1] + .0722 * linear[2]


def contrast_ratio(left: str, right: str) -> float:
    """Return the WCAG contrast ratio for two opaque hexadecimal colors."""

    high, low = sorted((_luminance(left), _luminance(right)), reverse=True)
    return (high + .05) / (low + .05)


# Stable study semantics use a shared baseline and never inherit the selected
# theme accent. Theme-specific differences follow the finalized Figma interface modes.
SEMANTIC_PALETTES: Mapping[str, Mapping[str, str]] = {'dark': {'status_new_fill': '#A2BFF2',
          'status_new_text': '#A2BFF2',
          'status_learning_fill': '#DDBF85',
          'status_learning_text': '#DDBF85',
          'status_review_fill': '#C6B4E3',
          'status_review_text': '#C6B4E3',
          'status_buried_fill': '#B3BAC7',
          'status_buried_text': '#B3BAC7',
          'status_success_fill': '#96CCB0',
          'status_success_text': '#96CCB0',
          'status_warning_fill': '#DDBF85',
          'status_warning_text': '#DDBF85',
          'status_danger_fill': '#E9A4AF',
          'status_danger_text': '#E9A4AF',
          'status_event_fill': '#D9BB83',
          'status_event_text': '#D9BB83'},
 'light': {'status_new_fill': '#345FAD',
           'status_new_text': '#345FAD',
           'status_learning_fill': '#825E20',
           'status_learning_text': '#825E20',
           'status_review_fill': '#704F98',
           'status_review_text': '#704F98',
           'status_buried_fill': '#5C6676',
           'status_buried_text': '#5C6676',
           'status_success_fill': '#2B7150',
           'status_success_text': '#2B7150',
           'status_warning_fill': '#825E20',
           'status_warning_text': '#825E20',
           'status_danger_fill': '#A43F55',
           'status_danger_text': '#A43F55',
           'status_event_fill': '#7D5B25',
           'status_event_text': '#7D5B25'}}


SEMANTIC_THEME_OVERRIDES: Mapping[str, Mapping[str, Mapping[str, str]]] = {'Sapphire Glass': {'dark': {'status_learning_fill': '#E9A4AF',
                             'status_learning_text': '#E9A4AF',
                             'status_review_fill': '#96CCB0',
                             'status_review_text': '#96CCB0',
                             'status_buried_fill': '#A8B3C6',
                             'status_buried_text': '#A8B3C6'},
                    'light': {'status_learning_fill': '#A43F55',
                              'status_learning_text': '#A43F55',
                              'status_review_fill': '#2B7150',
                              'status_review_text': '#2B7150',
                              'status_buried_fill': '#56667E',
                              'status_buried_text': '#56667E'}},
 'Emerald': {'dark': {'status_buried_fill': '#B0C2B7', 'status_buried_text': '#B0C2B7'},
             'light': {'status_buried_fill': '#577062', 'status_buried_text': '#577062'}},
 'High Contrast': {'dark': {'status_new_fill': '#BEDBFF',
                            'status_new_text': '#BEDBFF',
                            'status_learning_fill': '#F1D796',
                            'status_learning_text': '#F1D796',
                            'status_review_fill': '#E3D1FF',
                            'status_review_text': '#E3D1FF',
                            'status_buried_fill': '#DEE8F2',
                            'status_buried_text': '#DEE8F2',
                            'status_success_fill': '#97DCB3',
                            'status_success_text': '#97DCB3',
                            'status_warning_fill': '#FFE2A1',
                            'status_warning_text': '#FFE2A1',
                            'status_danger_fill': '#F69AA8',
                            'status_danger_text': '#F69AA8',
                            'status_event_fill': '#FFE2A1',
                            'status_event_text': '#FFE2A1'},
                   'light': {'status_new_fill': '#124C97',
                             'status_new_text': '#124C97',
                             'status_learning_fill': '#664300',
                             'status_learning_text': '#664300',
                             'status_review_fill': '#542A87',
                             'status_review_text': '#542A87',
                             'status_buried_fill': '#26384D',
                             'status_buried_text': '#26384D',
                             'status_success_fill': '#216C48',
                             'status_success_text': '#216C48',
                             'status_warning_fill': '#624400',
                             'status_warning_text': '#624400',
                             'status_danger_fill': '#AD304A',
                             'status_danger_text': '#AD304A',
                             'status_event_fill': '#624400',
                             'status_event_text': '#624400'}}}


# Reviews Due is a stable semantic visualization. The neutral background
# carries presence while the compact bottom marker carries three intensities.
PROJECTED_DUE_SCALES: Mapping[str, tuple[str, ...]] = {
    "light": ("", "#F4F2F5", "#F1EEF3", "#EDE9F0"),
    "dark": ("", "#242329", "#27242D", "#2B2632"),
}


REVIEWS_DUE_INDICATORS: Mapping[str, tuple[str, ...]] = {
    "light": ("", "#82708F", "#A58CB3", "#C6ACD1"),
    "dark": ("", "#82708F", "#A58CB3", "#C6ACD1"),
}


COMPLETION_SCALES: Mapping[str, Mapping[str, tuple[str, ...]]] = {'Sapphire Glass': {'dark': ('#202735', '#253045', '#36496D', '#46629A', '#6A8DD0', '#90AFED'),
                    'light': ('#F1F3F8', '#E7EEFA', '#C1D2F0', '#98B1E1', '#678BD2', '#2F55A4')},
 'Graphite': {'dark': ('#24262C', '#2E3034', '#45494F', '#5D646D', '#878E99', '#A9B0BA'),
              'light': ('#F2F2F4', '#ECEDF0', '#CED1D6', '#ACB1B9', '#858D99', '#515A67')},
 'Emerald': {'dark': ('#202C28', '#21362A', '#2D523D', '#367151', '#5A9F78', '#83BF9C'),
             'light': ('#F0F5F2', '#E5F1E9', '#BDD9C7', '#90BEA2', '#549E75', '#036B41')},
 'High Contrast': {'dark': ('#151B23', '#013441', '#00566B', '#087E9B', '#09B6DF', '#A2E3FA'),
                   'light': ('#FFFFFF', '#E0F5FD', '#96D9F1', '#33B5DA', '#0484A3', '#024A5D')}}


# Every saved palette identifier owns an authored light and dark ladder.  These
# values are deliberately explicit: composing a translucent hue over white or
# aliasing every identifier to the dashboard theme made the Settings choices
# visually indistinguishable and produced surprising changes over host images.
HEATMAP_COMPLETION_SCALES: Mapping[
    str, Mapping[str, Mapping[str, tuple[str, ...]]]
] = {'Sapphire Glass': {'Sapphire': {'dark': ('#202735',
                                          '#253045',
                                          '#36496D',
                                          '#46629A',
                                          '#6A8DD0',
                                          '#90AFED'),
                                 'light': ('#F1F3F8',
                                           '#E7EEFA',
                                           '#C1D2F0',
                                           '#98B1E1',
                                           '#678BD2',
                                           '#2F55A4')},
                    'Amethyst': {'dark': ('#202735',
                                          '#312D40',
                                          '#4B4364',
                                          '#675A8D',
                                          '#9282C0',
                                          '#B3A6DE'),
                                 'light': ('#F1F3F8',
                                           '#EEECF7',
                                           '#D2CCE9',
                                           '#B3AAD6',
                                           '#9080C2',
                                           '#5F4A93')},
                    'Glacier': {'dark': ('#202735',
                                         '#21333B',
                                         '#2C4E5C',
                                         '#356B80',
                                         '#5897B1',
                                         '#82B9D0'),
                                'light': ('#F1F3F8',
                                          '#E5EFF4',
                                          '#BCD6E1',
                                          '#8EB9CB',
                                          '#5296B1',
                                          '#00637F')},
                    'Sea Glass': {'dark': ('#202735',
                                           '#24352D',
                                           '#335044',
                                           '#3F6E5B',
                                           '#649B84',
                                           '#8BBCA7'),
                                  'light': ('#F1F3F8',
                                            '#E7F0EC',
                                            '#C0D7CD',
                                            '#95BBAA',
                                            '#5F9B82',
                                            '#1A684E')}},
 'Graphite': {'Slate': {'dark': ('#24262C', '#2E3034', '#45494F', '#5D646D', '#878E99', '#A9B0BA'),
                        'light': ('#F2F2F4', '#ECEDF0', '#CED1D6', '#ACB1B9', '#858D99', '#515A67')},
              'Steel': {'dark': ('#24262C', '#28323B', '#3A4B5B', '#4B667F', '#7192AF', '#96B3CE'),
                        'light': ('#F2F2F4', '#E8EEF4', '#C5D3E0', '#9DB4C9', '#6E90AF', '#355D7F')},
              'Plum': {'dark': ('#24262C', '#372C37', '#554254', '#755874', '#A480A2', '#C4A3C2'),
                       'light': ('#F2F2F4', '#F2EBF1', '#DBCBDA', '#C1A7C0', '#A47DA2', '#724870')},
              'Mint': {'dark': ('#24262C', '#27342B', '#394F3F', '#496D55', '#6F997C', '#94BB9F'),
                       'light': ('#F2F2F4', '#E8F0EA', '#C4D7C9', '#9CBAA4', '#6B9979', '#316644')}},
 'Emerald': {'Emerald': {'dark': ('#202C28', '#21362A', '#2D523D', '#367151', '#5A9F78', '#83BF9C'),
                         'light': ('#F0F5F2', '#E5F1E9', '#BDD9C7', '#90BEA2', '#549E75', '#036B41')},
             'Jade': {'dark': ('#202C28', '#20352F', '#2C5148', '#337061', '#579D8B', '#81BEAD'),
                      'light': ('#F0F5F2', '#E5F1ED', '#BCD8D0', '#8EBDAF', '#509D89', '#016957')},
             'Moss': {'dark': ('#202C28', '#2F3223', '#474C31', '#61683E', '#8A9462', '#ACB588'),
                      'light': ('#F0F5F2', '#EDEFE6', '#CFD4BE', '#AEB693', '#89925D', '#56601F')},
             'Lagoon': {'dark': ('#202C28', '#1F3536', '#285153', '#2D6F73', '#509CA0', '#7CBDC1'),
                        'light': ('#F0F5F2', '#E4F0F1', '#BAD8DA', '#8ABCBF', '#499BA0', '#01666B')}},
 'High Contrast': {'Cyan': {'dark': ('#151B23', '#013441', '#00566B', '#087E9B', '#09B6DF', '#A2E3FA'),
                            'light': ('#FFFFFF', '#E0F5FD', '#96D9F1', '#33B5DA', '#0484A3', '#024A5D')},
                   'Gold': {'dark': ('#151B23', '#3B2B01', '#624900', '#8E6C06', '#C99E2F', '#EDD5A0'),
                            'light': ('#FFFFFF', '#F8F0DE', '#E4CB95', '#C69F41', '#967103', '#543F02')},
                   'Magenta': {'dark': ('#151B23', '#431F3B', '#6F3463', '#9E528D', '#D883C4', '#F7C6EA'),
                               'light': ('#FFFFFF',
                                         '#FCEBF7',
                                         '#EEBCE1',
                                         '#D487C1',
                                         '#A35993',
                                         '#632957')},
                   'Monochrome': {'dark': ('#151B23',
                                           '#2E2E2E',
                                           '#4D4D4D',
                                           '#717171',
                                           '#A4A4A4',
                                           '#D7D7D7'),
                                  'light': ('#FFFFFF',
                                            '#F1F1F1',
                                            '#CECECE',
                                            '#A4A4A4',
                                            '#777777',
                                            '#424242')}}}


# Shared surfaces from the redesign; saved IDs and semantic roles stay stable.
CORE_PALETTES: Mapping[str, Mapping[str, Mapping[str, str]]] = {'Sapphire Glass': {'dark': {'ui_text_secondary': '#A8B3C6',
                             'ui_canvas': '#10141C',
                             'ui_text_disabled': '#8492AA',
                             'ui_disabled_border': '#303A4A',
                             'ui_accent_soft': '#293A5B',
                             'ui_text_primary': '#ECEFF6',
                             'ui_border_strong': '#43516A',
                             'ui_skeleton_highlight': '#2C3749',
                             'ui_skeleton_base': '#222B3A',
                             'ui_control_pressed': '#2C3749',
                             'ui_surface_1': '#191F2B',
                             'ui_accent': '#A3BEFA',
                             'ui_accent_border': '#43516A',
                             'ui_focus': '#C4D6FF',
                             'ui_accent_pressed': '#85A5E7',
                             'ui_accent_hover': '#C0D2FF',
                             'ui_on_accent': '#14213A',
                             'ui_control_background': '#222B3A',
                             'ui_control_hover': '#2C3749',
                             'ui_border_subtle': '#303A4A',
                             'ui_border_default': '#303A4A',
                             'ui_control_border': '#43516A',
                             'ui_divider': '#303A4A',
                             'ui_text_tertiary': '#8492AA',
                             'ui_progress_track': '#222B3A',
                             'ui_surface_2': '#222B3A',
                             'ui_surface_3': '#222B3A',
                             'ui_eyebrow': '#A8B3C6',
                             'progress_complete': '#A3BEFA',
                             'calendar_today_background': '#14213A',
                             'calendar_today_text': '#F3F6FD'},
                    'light': {'ui_text_secondary': '#56667E',
                              'ui_canvas': '#F5F7FB',
                              'ui_text_disabled': '#6A7990',
                              'ui_disabled_border': '#DCE3EE',
                              'ui_accent_soft': '#EBF0FC',
                              'ui_text_primary': '#243148',
                              'ui_border_strong': '#B6C2D4',
                              'ui_skeleton_highlight': '#E8EDF6',
                              'ui_skeleton_base': '#F0F3F8',
                              'ui_control_pressed': '#E8EDF6',
                              'ui_surface_1': '#FFFFFF',
                              'ui_accent': '#335DB6',
                              'ui_accent_border': '#B6C2D4',
                              'ui_focus': '#315CAD',
                              'ui_accent_pressed': '#234185',
                              'ui_accent_hover': '#294D9B',
                              'ui_on_accent': '#FFFFFF',
                              'ui_control_background': '#F0F3F8',
                              'ui_control_hover': '#E8EDF6',
                              'ui_border_subtle': '#DCE3EE',
                              'ui_border_default': '#DCE3EE',
                              'ui_control_border': '#B6C2D4',
                              'ui_divider': '#DCE3EE',
                              'ui_text_tertiary': '#6A7990',
                              'ui_progress_track': '#F0F3F8',
                              'ui_surface_2': '#F0F3F8',
                              'ui_surface_3': '#F0F3F8',
                              'ui_eyebrow': '#56667E',
                              'progress_complete': '#335DB6',
                              'calendar_today_background': '#FFFFFF',
                              'calendar_today_text': '#335DB6'}},
 'Graphite': {'dark': {'ui_text_secondary': '#B3BAC7',
                       'ui_canvas': '#131519',
                       'ui_text_disabled': '#929CAC',
                       'ui_disabled_border': '#333944',
                       'ui_accent_soft': '#343C4A',
                       'ui_text_primary': '#F0F1F5',
                       'ui_border_strong': '#596474',
                       'ui_skeleton_highlight': '#333943',
                       'ui_skeleton_base': '#272B33',
                       'ui_control_pressed': '#333943',
                       'ui_surface_1': '#1D2026',
                       'ui_accent': '#C4CBD8',
                       'ui_accent_border': '#596474',
                       'ui_focus': '#E1E7F4',
                       'ui_accent_pressed': '#AAB4C4',
                       'ui_accent_hover': '#DDE2EC',
                       'ui_on_accent': '#202A3B',
                       'ui_control_background': '#272B33',
                       'ui_control_hover': '#333943',
                       'ui_border_subtle': '#333944',
                       'ui_border_default': '#333944',
                       'ui_control_border': '#596474',
                       'ui_divider': '#333944',
                       'ui_text_tertiary': '#929CAC',
                       'ui_progress_track': '#272B33',
                       'ui_surface_2': '#272B33',
                       'ui_surface_3': '#272B33',
                       'ui_eyebrow': '#B3BAC7',
                       'progress_complete': '#C4CBD8',
                       'calendar_today_background': '#202A3B',
                       'calendar_today_text': '#F3F6FD'},
              'light': {'ui_text_secondary': '#5C6676',
                        'ui_canvas': '#F5F6F8',
                        'ui_text_disabled': '#758092',
                        'ui_disabled_border': '#DFE3E9',
                        'ui_accent_soft': '#ECF0F5',
                        'ui_text_primary': '#282F3B',
                        'ui_border_strong': '#B7C0CD',
                        'ui_skeleton_highlight': '#E6EAF0',
                        'ui_skeleton_base': '#F0F2F5',
                        'ui_control_pressed': '#E6EAF0',
                        'ui_surface_1': '#FFFFFF',
                        'ui_accent': '#46576F',
                        'ui_accent_border': '#B7C0CD',
                        'ui_focus': '#3B506D',
                        'ui_accent_pressed': '#2C394E',
                        'ui_accent_hover': '#35445C',
                        'ui_on_accent': '#FFFFFF',
                        'ui_control_background': '#F0F2F5',
                        'ui_control_hover': '#E6EAF0',
                        'ui_border_subtle': '#DFE3E9',
                        'ui_border_default': '#DFE3E9',
                        'ui_control_border': '#B7C0CD',
                        'ui_divider': '#DFE3E9',
                        'ui_text_tertiary': '#758092',
                        'ui_progress_track': '#F0F2F5',
                        'ui_surface_2': '#F0F2F5',
                        'ui_surface_3': '#F0F2F5',
                        'ui_eyebrow': '#5C6676',
                        'progress_complete': '#46576F',
                        'calendar_today_background': '#FFFFFF',
                        'calendar_today_text': '#46576F'}},
 'Emerald': {'dark': {'ui_text_secondary': '#B0C2B7',
                      'ui_canvas': '#101814',
                      'ui_text_disabled': '#889F91',
                      'ui_disabled_border': '#31483A',
                      'ui_accent_soft': '#294A37',
                      'ui_text_primary': '#EDF5EF',
                      'ui_border_strong': '#597B66',
                      'ui_skeleton_highlight': '#2D4538',
                      'ui_skeleton_base': '#23352B',
                      'ui_control_pressed': '#2D4538',
                      'ui_surface_1': '#192620',
                      'ui_accent': '#91CEAC',
                      'ui_accent_border': '#597B66',
                      'ui_focus': '#C8EDD5',
                      'ui_accent_pressed': '#73B68F',
                      'ui_accent_hover': '#B4E1C5',
                      'ui_on_accent': '#122C1D',
                      'ui_control_background': '#23352B',
                      'ui_control_hover': '#2D4538',
                      'ui_border_subtle': '#31483A',
                      'ui_border_default': '#31483A',
                      'ui_control_border': '#597B66',
                      'ui_divider': '#31483A',
                      'ui_text_tertiary': '#889F91',
                      'ui_progress_track': '#23352B',
                      'ui_surface_2': '#23352B',
                      'ui_surface_3': '#23352B',
                      'ui_eyebrow': '#B0C2B7',
                      'progress_complete': '#91CEAC',
                      'calendar_today_background': '#122C1D',
                      'calendar_today_text': '#F3F6FD'},
             'light': {'ui_text_secondary': '#577062',
                       'ui_canvas': '#F3F7F4',
                       'ui_text_disabled': '#6F887B',
                       'ui_disabled_border': '#DCE7DF',
                       'ui_accent_soft': '#E8F3EB',
                       'ui_text_primary': '#263D30',
                       'ui_border_strong': '#A5BEAE',
                       'ui_skeleton_highlight': '#E3EEE7',
                       'ui_skeleton_base': '#EFF5F1',
                       'ui_control_pressed': '#E3EEE7',
                       'ui_surface_1': '#FFFFFF',
                       'ui_accent': '#2F7150',
                       'ui_accent_border': '#A5BEAE',
                       'ui_focus': '#246940',
                       'ui_accent_pressed': '#1C4D35',
                       'ui_accent_hover': '#245D41',
                       'ui_on_accent': '#FFFFFF',
                       'ui_control_background': '#EFF5F1',
                       'ui_control_hover': '#E3EEE7',
                       'ui_border_subtle': '#DCE7DF',
                       'ui_border_default': '#DCE7DF',
                       'ui_control_border': '#A5BEAE',
                       'ui_divider': '#DCE7DF',
                       'ui_text_tertiary': '#6F887B',
                       'ui_progress_track': '#EFF5F1',
                       'ui_surface_2': '#EFF5F1',
                       'ui_surface_3': '#EFF5F1',
                       'ui_eyebrow': '#577062',
                       'progress_complete': '#2F7150',
                       'calendar_today_background': '#FFFFFF',
                       'calendar_today_text': '#2F7150'}},
 'High Contrast': {'dark': {'ui_text_secondary': '#DCE7F3',
                            'ui_canvas': '#070B10',
                            'ui_text_disabled': '#A8BACD',
                            'ui_disabled_border': '#8295A9',
                            'ui_accent_soft': '#214153',
                            'ui_text_primary': '#FFFFFF',
                            'ui_border_strong': '#AABCDA',
                            'ui_skeleton_highlight': '#304456',
                            'ui_skeleton_base': '#1C2935',
                            'ui_control_pressed': '#304456',
                            'ui_surface_1': '#111820',
                            'ui_accent': '#A5DEEE',
                            'ui_accent_border': '#AABCDA',
                            'ui_focus': '#FFFFFF',
                            'ui_accent_pressed': '#7AC4DD',
                            'ui_accent_hover': '#CBF0F8',
                            'ui_on_accent': '#0A202D',
                            'ui_control_background': '#1C2935',
                            'ui_control_hover': '#304456',
                            'ui_border_subtle': '#8295A9',
                            'ui_border_default': '#8295A9',
                            'ui_control_border': '#AABCDA',
                            'ui_divider': '#8295A9',
                            'ui_text_tertiary': '#A8BACD',
                            'ui_progress_track': '#1C2935',
                            'ui_surface_2': '#1C2935',
                            'ui_surface_3': '#1C2935',
                            'ui_eyebrow': '#DCE7F3',
                            'progress_complete': '#A5DEEE',
                            'calendar_today_background': '#0A202D',
                            'calendar_today_text': '#F3F6FD'},
                   'light': {'ui_text_secondary': '#2E4258',
                             'ui_canvas': '#FFFFFF',
                             'ui_text_disabled': '#516980',
                             'ui_disabled_border': '#62758A',
                             'ui_accent_soft': '#E6F2F7',
                             'ui_text_primary': '#13202E',
                             'ui_border_strong': '#41586E',
                             'ui_skeleton_highlight': '#E1EAF1',
                             'ui_skeleton_base': '#F1F5F8',
                             'ui_control_pressed': '#E1EAF1',
                             'ui_surface_1': '#FFFFFF',
                             'ui_accent': '#18536B',
                             'ui_accent_border': '#41586E',
                             'ui_focus': '#0D3E59',
                             'ui_accent_pressed': '#0B3144',
                             'ui_accent_hover': '#103F55',
                             'ui_on_accent': '#FFFFFF',
                             'ui_control_background': '#F1F5F8',
                             'ui_control_hover': '#E1EAF1',
                             'ui_border_subtle': '#62758A',
                             'ui_border_default': '#62758A',
                             'ui_control_border': '#41586E',
                             'ui_divider': '#62758A',
                             'ui_text_tertiary': '#516980',
                             'ui_progress_track': '#F1F5F8',
                             'ui_surface_2': '#F1F5F8',
                             'ui_surface_3': '#F1F5F8',
                             'ui_eyebrow': '#2E4258',
                             'progress_complete': '#18536B',
                             'calendar_today_background': '#FFFFFF',
                             'calendar_today_text': '#18536B'}}}


HEATMAP_PRESET_NAMES: Mapping[str, tuple[str, ...]] = {
    "Sapphire Glass": ("Sapphire", "Amethyst", "Glacier", "Sea Glass"),
    "Graphite": ("Slate", "Steel", "Plum", "Mint"),
    "Emerald": ("Emerald", "Jade", "Moss", "Lagoon"),
    "High Contrast": ("Cyan", "Gold", "Magenta", "Monochrome"),
}


HEATMAP_COMPLETION_TEXT = {'Sapphire Glass': {'Sapphire': {'dark': ('#F3F6FD',
                                          '#F3F6FD',
                                          '#F3F6FD',
                                          '#F3F6FD',
                                          '#101C2D',
                                          '#101C2D'),
                                 'light': ('#101C2D',
                                           '#101C2D',
                                           '#101C2D',
                                           '#101C2D',
                                           '#101C2D',
                                           '#F3F6FD')},
                    'Amethyst': {'dark': ('#F3F6FD',
                                          '#F3F6FD',
                                          '#F3F6FD',
                                          '#F3F6FD',
                                          '#101C2D',
                                          '#101C2D'),
                                 'light': ('#101C2D',
                                           '#101C2D',
                                           '#101C2D',
                                           '#101C2D',
                                           '#101C2D',
                                           '#F3F6FD')},
                    'Glacier': {'dark': ('#F3F6FD',
                                         '#F3F6FD',
                                         '#F3F6FD',
                                         '#F3F6FD',
                                         '#101C2D',
                                         '#101C2D'),
                                'light': ('#101C2D',
                                          '#101C2D',
                                          '#101C2D',
                                          '#101C2D',
                                          '#101C2D',
                                          '#F3F6FD')},
                    'Sea Glass': {'dark': ('#F3F6FD',
                                           '#F3F6FD',
                                           '#F3F6FD',
                                           '#F3F6FD',
                                           '#101C2D',
                                           '#101C2D'),
                                  'light': ('#101C2D',
                                            '#101C2D',
                                            '#101C2D',
                                            '#101C2D',
                                            '#101C2D',
                                            '#F3F6FD')}},
 'Graphite': {'Slate': {'dark': ('#F3F6FD', '#F3F6FD', '#F3F6FD', '#F3F6FD', '#101C2D', '#101C2D'),
                        'light': ('#101C2D', '#101C2D', '#101C2D', '#101C2D', '#101C2D', '#F3F6FD')},
              'Steel': {'dark': ('#F3F6FD', '#F3F6FD', '#F3F6FD', '#F3F6FD', '#101C2D', '#101C2D'),
                        'light': ('#101C2D', '#101C2D', '#101C2D', '#101C2D', '#101C2D', '#F3F6FD')},
              'Plum': {'dark': ('#F3F6FD', '#F3F6FD', '#F3F6FD', '#F3F6FD', '#101C2D', '#101C2D'),
                       'light': ('#101C2D', '#101C2D', '#101C2D', '#101C2D', '#101C2D', '#F3F6FD')},
              'Mint': {'dark': ('#F3F6FD', '#F3F6FD', '#F3F6FD', '#F3F6FD', '#101C2D', '#101C2D'),
                       'light': ('#101C2D', '#101C2D', '#101C2D', '#101C2D', '#101C2D', '#F3F6FD')}},
 'Emerald': {'Emerald': {'dark': ('#F3F6FD', '#F3F6FD', '#F3F6FD', '#F3F6FD', '#10271F', '#10271F'),
                         'light': ('#10271F', '#10271F', '#10271F', '#10271F', '#10271F', '#F3F6FD')},
             'Jade': {'dark': ('#F3F6FD', '#F3F6FD', '#F3F6FD', '#F3F6FD', '#10271F', '#10271F'),
                      'light': ('#10271F', '#10271F', '#10271F', '#10271F', '#10271F', '#F3F6FD')},
             'Moss': {'dark': ('#F3F6FD', '#F3F6FD', '#F3F6FD', '#F3F6FD', '#10271F', '#10271F'),
                      'light': ('#10271F', '#10271F', '#10271F', '#10271F', '#10271F', '#F3F6FD')},
             'Lagoon': {'dark': ('#F3F6FD', '#F3F6FD', '#F3F6FD', '#F3F6FD', '#10271F', '#10271F'),
                        'light': ('#10271F', '#10271F', '#10271F', '#10271F', '#10271F', '#F3F6FD')}},
 'High Contrast': {'Cyan': {'dark': ('#FFFFFF', '#FFFFFF', '#FFFFFF', '#FFFFFF', '#000000', '#000000'),
                            'light': ('#000000', '#000000', '#000000', '#000000', '#000000', '#FFFFFF')},
                   'Gold': {'dark': ('#FFFFFF', '#FFFFFF', '#FFFFFF', '#FFFFFF', '#000000', '#000000'),
                            'light': ('#000000', '#000000', '#000000', '#000000', '#000000', '#FFFFFF')},
                   'Magenta': {'dark': ('#FFFFFF', '#FFFFFF', '#FFFFFF', '#FFFFFF', '#000000', '#000000'),
                               'light': ('#000000',
                                         '#000000',
                                         '#000000',
                                         '#000000',
                                         '#FFFFFF',
                                         '#FFFFFF')},
                   'Monochrome': {'dark': ('#FFFFFF',
                                           '#FFFFFF',
                                           '#FFFFFF',
                                           '#FFFFFF',
                                           '#000000',
                                           '#000000'),
                                  'light': ('#000000',
                                            '#000000',
                                            '#000000',
                                            '#000000',
                                            '#000000',
                                            '#FFFFFF')}}}


def _heat_text(fill: str, primary: str) -> str:
    """Choose the strongest readable date color for an authored heat cell."""

    candidates = (primary, "#FFFFFF", "#0B1116", "#000000")
    return max(candidates, key=lambda candidate: contrast_ratio(candidate, fill))


def _heat_tokens(
    theme_name: str,
    variant: str,
    core: Mapping[str, str],
    preset_name: str | None = None,
) -> Theme:
    selected = preset_name or HEATMAP_PRESET_NAMES[theme_name][0]
    completion = HEATMAP_COMPLETION_SCALES[theme_name][selected][variant]
    complete_text = HEATMAP_COMPLETION_TEXT[theme_name][selected][variant]
    return {
        **{"heat_complete_{}".format(level): color for level, color in enumerate(completion)},
        **{"heat_complete_text_{}".format(level): color for level, color in enumerate(complete_text)},
        **{
            "heat_due_bg_{}".format(level): PROJECTED_DUE_SCALES[variant][level]
            for level in range(1, 4)
        },
        **{
            "heat_due_mark_{}".format(level): REVIEWS_DUE_INDICATORS[variant][level]
            for level in range(1, 4)
        },
    }


def _build_theme(theme_name: str, variant: str) -> Theme:
    core = dict(CORE_PALETTES[theme_name][variant])
    skeleton_opacity = .10 if variant == "light" else .16
    core.setdefault("ui_skeleton_base", composite_color(
        core["ui_accent"], core["ui_surface_2"], skeleton_opacity
    ))
    core.setdefault("ui_skeleton_highlight", composite_color(
        core["ui_accent"], core["ui_surface_2"], skeleton_opacity * 1.8
    ))
    core["ui_shadow_card"] = "none"
    core["ui_shadow_overlay"] = (
        "none" if theme_name == "High Contrast"
        else "0 4px 12px rgba(16, 24, 40, 0.10), 0 16px 32px rgba(16, 24, 40, 0.12)"
        if variant == "light"
        else "0 2px 8px rgba(0, 0, 0, 0.48), 0 18px 38px rgba(0, 0, 0, 0.30)"
    )
    core.update(SEMANTIC_PALETTES[variant])
    core.update(SEMANTIC_THEME_OVERRIDES.get(theme_name, {}).get(variant, {}))
    core.update(_heat_tokens(theme_name, variant, core))
    core.update({
        "ui_disabled_surface": core["ui_surface_3"],
        "ui_disabled_border": core["ui_border_default"],
        "ui_control_hover": core.get("ui_control_hover", core["ui_accent_soft"]),
        "ui_control_pressed": core.get("ui_control_pressed", core["ui_surface_3"]),
        "ui_overlay_surface": core["ui_surface_1"],
        "ui_scrollbar_track": core["ui_surface_2"],
        "ui_scrollbar_thumb": core["ui_border_strong"],
        "ui_scrollbar_thumb_hover": core["ui_accent_border"],
        "status_warning_soft": composite_color(core["status_warning_fill"], core["ui_surface_1"], .13),
        "status_danger_soft": composite_color(core["status_danger_fill"], core["ui_surface_1"], .13),
        "calendar_empty_bg": core["heat_complete_0"],
        "calendar_outside_bg": core["ui_surface_2"],
        "calendar_outside_text": core["ui_text_secondary"],
        "calendar_future_bg": core["ui_surface_3"],
        "calendar_future_text": core["ui_text_secondary"],
        "calendar_footer_bg": core["ui_surface_2"],
        "calendar_today_ring": core["ui_accent"],
        "calendar_selected_ring": core["ui_accent"],
        "calendar_ring_halo": core["ui_surface_1"],
        "calendar_event_halo": core["ui_surface_1"],
        "theme_name": theme_name,
        "color_mode": variant,
    })
    return core


# Insertion order is the public Settings order. Theme identifiers are stable.
PRESETS: Mapping[str, Mapping[str, Theme]] = {
    theme_name: {
        variant: _build_theme(theme_name, variant)
        for variant in ("light", "dark")
    }
    for theme_name in ("Sapphire Glass", "Graphite", "Emerald", "High Contrast")
}


# Historical heatmap preference identifiers remain valid.  Each identifier now
# resolves to its own authored hue ladder while retaining the stable theme
# boundary and the same persisted value.
HEATMAP_PRESETS: Mapping[str, Mapping[str, Mapping[str, Theme]]] = {
    theme_name: {
        preset_name: {
            variant: {
                key: value
                for key, value in _heat_tokens(
                    theme_name,
                    variant,
                    CORE_PALETTES[theme_name][variant],
                    preset_name,
                ).items()
                if key.startswith("heat_complete_")
            }
            for variant in ("light", "dark")
        }
        for preset_name in HEATMAP_PRESET_NAMES[theme_name]
    }
    for theme_name in PRESETS
}


DEFAULT_HEATMAP_PRESETS: Mapping[str, str] = {
    theme_name: names[0] for theme_name, names in HEATMAP_PRESET_NAMES.items()
}
DEFAULT_HEATMAP_PRESET = DEFAULT_HEATMAP_PRESETS["Sapphire Glass"]


def resolve_theme(
    preset: object,
    mode: object,
    anki_dark: bool,
    heatmap_preset: object = DEFAULT_HEATMAP_PRESET,
) -> Theme:
    """Resolve one complete token set while retaining saved preference IDs."""

    name = preset if isinstance(preset, str) and preset in PRESETS else "Sapphire Glass"
    selected_mode = mode if mode in {"auto", "light", "dark"} else "auto"
    variant = "dark" if (
        selected_mode == "dark" or (selected_mode == "auto" and anki_dark)
    ) else "light"
    available = HEATMAP_PRESETS[name]
    calendar_name = (
        heatmap_preset
        if isinstance(heatmap_preset, str) and heatmap_preset in available
        else DEFAULT_HEATMAP_PRESETS[name]
    )
    resolved = dict(PRESETS[name][variant])
    resolved.update(available[calendar_name][variant])
    resolved["calendar_empty_bg"] = resolved["heat_complete_0"]
    resolved["heatmap_preset"] = calendar_name
    return resolved
