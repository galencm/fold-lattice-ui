# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2018, Galen Curwen-McAdams

def keybindings():
    actions = {}
    # app always handled
    actions["app"] = {}
    actions["app"]["app_exit"] = [["c"], ["ctrl"]]
    # actions["app"]["tab_next"] = [["left"], ["ctrl"]]
    # actions["app"]["tab_previous"] = [["right"], ["ctrl"]]
    # tabs have different actions / bindings
    # handled if tab is currently active / visible
    # folds
    actions["folds"] = {}
    actions["folds"]["contents_view_down"] = [["down"], []]
    actions["folds"]["contents_view_up"] = [["up"], []]
    actions["folds"]["contents_view_left"] = [["left"], []]
    actions["folds"]["contents_view_right"] = [["right"], []]
    actions["folds"]["contents_grow_columns"] = [["right"], ["ctrl"]]
    actions["folds"]["contents_shrink_columns"] = [["left"], ["ctrl"]]
    actions["folds"]["fold_shrink_width"] = [["left"], ["shift", "ctrl"]]
    actions["folds"]["fold_grow_width"] = [["right"], ["shift", "ctrl"]]
    actions["folds"]["fold_unfold_next"] = [["left"], ["shift"]]
    actions["folds"]["fold_unfold_previous"] = [["right"], ["shift"]]
    actions["folds"]["contents_enlarge"] = [["up"], ["shift"]]
    actions["folds"]["contents_shrink"] = [["down"], ["shift"]]
    actions["folds"]["contents_enlarge_all"] = [["up"], ["ctrl"]]
    actions["folds"]["contents_shrink_all"] = [["down"], ["ctrl"]]

    return actions