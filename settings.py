#########################################################################################
#
# settings.py - Rev. 1.0
# Copyright (C) 2021 by Joseph B. Attili, aa2il AT arrl DOT net
#
# Gui for basic settings.
#
############################################################################################
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
#########################################################################################

import sys
import json
if sys.version_info[0]==3:
    from tkinter import *
    import tkinter.font
else:
    from Tkinter import *
    import tkFont

#########################################################################################

class SETTINGS():
    def __init__(self,root,P):
        self.P = P
        
        if root:
            self.win=Toplevel(root)
        else:
            self.win = Tk()
        self.win.title("Settings")

        row=0
        Label(self.win, text='My Call:').grid(row=row, column=0)
        self.call = Entry(self.win)
        self.call.grid(row=row,column=1,sticky=E+W)
        #self.call.delete(0, END)
        try:
            self.call.insert(0,P.MY_CALL)
        except:
            pass

        row+=1
        button = Button(self.win, text="OK",command=self.Dismiss)
        button.grid(row=row,column=1,sticky=E+W)

        self.win.update()
        self.win.deiconify()

    def Dismiss(self):
        self.P.SETTINGS = {'MY_CALL' : self.call.get().upper()}
        
        with open(self.P.RCFILE, "w") as outfile:
            json.dump(self.P.SETTINGS, outfile)
        
        self.win.destroy()

        
