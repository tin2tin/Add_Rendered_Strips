# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

bl_info = {
    "name": "Add Rendered Strips",
    "author": "tintwotin",
    "version": (1, 0),
    "blender": (3, 4, 0),
    "location": "Add > Rendered Strips",
    "description": "Render selected strips to hard disk and add the rendered files as movie strips to the original scene in the first free channel",
    "warning": "",
    "doc_url": "",
    "category": "Sequencer",
}

import os
import bpy


class RenderSelectedStripsOperator(bpy.types.Operator):
    """Render selected strips to hard disk and add the rendered files as movie strips to the original scene in the first free channel"""

    bl_idname = "sequencer.render_selected_strips"
    bl_label = "Rendered Strips"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context and context.scene and context.scene.sequence_editor

    def execute(self, context):
        # Check for the context and selected strips
        if not context or not context.scene or not context.scene.sequence_editor:
            self.report({"ERROR"}, "No valid context or selected strips")
            return {"CANCELLED"}

        # Get the current scene and sequencer
        current_scene = context.scene
        sequencer = current_scene.sequence_editor
        current_frame_old = bpy.context.scene.frame_current

        # Check if there are any selected strips
        if not any(strip.select for strip in sequencer.sequences_all):
            self.report({"ERROR"}, "No strips selected")
            return {"CANCELLED"}

        # Get the selected sequences in the sequencer
        selected_sequences = bpy.context.selected_sequences

        # Get the first empty channel above all strips
        insert_channel_total = 1
        for s in sequencer.sequences_all:
            if s.channel >= insert_channel_total:
                insert_channel_total = s.channel + 1

        # Loop over the selected strips in the current scene
        for strip in selected_sequences:
            if strip.type in {"MOVIE", "IMAGE", "SOUND", "SCENE", "TEXT", "COLOR", "META"}:

                # Deselect all strips in the current scene
                for s in sequencer.sequences_all:
                    s.select = False

                # Select the current strip in the current scene
                strip.select = True

                # Store current frame for later
                bpy.context.scene.frame_current = int(strip.frame_start)

                # Copy the strip to the clipboard
                bpy.ops.sequencer.copy()

                # Create a new scene
                #new_scene = bpy.data.scenes.new(name="New Scene")

                # Create a new scene
                new_scene = bpy.ops.scene.new(type='EMPTY')

                # Get the newly created scene
                new_scene = bpy.context.scene

                # Add a sequencer to the new scene
                new_scene.sequence_editor_create()

                # Set the new scene as the active scene
                context.window.scene = new_scene

                # Copy the scene properties from the current scene to the new scene
                new_scene.render.resolution_x = current_scene.render.resolution_x
                new_scene.render.resolution_y = current_scene.render.resolution_y
                new_scene.render.resolution_percentage = (current_scene.render.resolution_percentage)
                new_scene.render.pixel_aspect_x = current_scene.render.pixel_aspect_x
                new_scene.render.pixel_aspect_y = current_scene.render.pixel_aspect_y
                new_scene.render.fps = current_scene.render.fps
                new_scene.render.fps_base = current_scene.render.fps_base
                new_scene.render.sequencer_gl_preview = (current_scene.render.sequencer_gl_preview)
                new_scene.render.use_sequencer_override_scene_strip = (current_scene.render.use_sequencer_override_scene_strip)
                new_scene.world = current_scene.world

                # Paste the strip from the clipboard to the new scene
                bpy.ops.sequencer.paste()

                # Get the new strip in the new scene
                new_strip = (new_scene.sequence_editor.active_strip) = bpy.context.selected_sequences[0]

                # Set the range in the new scene to fit the pasted strip
                new_scene.frame_start = int(new_strip.frame_final_start)
                new_scene.frame_end = (int(new_strip.frame_final_start + new_strip.frame_final_duration)-1)

                # Set the name of the file
                src_name = strip.name
                src_dir = ""
                src_ext = ".mp4"
                
                # Set the path to the blend file
                blend_path = bpy.data.filepath
                if blend_path:
                    src_dir = bpy.path.abspath(os.path.dirname(blend_path))
                else:
                    src_dir = bpy.path.abspath(os.path.expanduser("~"))

                # Set the render settings for rendering animation with FFmpeg and MP4 with sound
                bpy.context.scene.render.image_settings.file_format = "FFMPEG"
                bpy.context.scene.render.ffmpeg.format = "MPEG4"
                bpy.context.scene.render.ffmpeg.audio_codec = "AAC"

                # Create a new folder for the rendered files
                rendered_dir = os.path.join(src_dir, src_name + "_rendered")
                if not os.path.exists(rendered_dir):
                    os.makedirs(rendered_dir)

                # Set the output path for the rendering
                output_path = os.path.join(
                    rendered_dir, src_name + "_rendered" + src_ext
                )
                new_scene.render.filepath = output_path

                # Render the strip to hard disk
                bpy.ops.render.opengl(animation=True, sequencer=True)

                # Delete the new scene
                bpy.data.scenes.remove(new_scene, do_unlink=True)

                # Set the original scene as the active scene
                context.window.scene = current_scene

                # Reset to total top channel
                insert_channel = insert_channel_total

                # Loop until an empty space is found
                while True:
                    # Check if there are any strips in the target channel that overlap with the range of the selected strips
                    if not any(
                        s.channel == insert_channel
                        and s.frame_final_start
                        < strip.frame_final_end
                        and s.frame_final_end
                        > strip.frame_final_start
                        for s in sequencer.sequences_all
                    ):
                        break
                    else:
                        # Increment the target channel
                        insert_channel += 1

                if strip.type == "SOUND":
                    # Insert the rendered file as a sound strip in the original scene without video.
                    bpy.ops.sequencer.sound_strip_add(
                        channel=insert_channel,
                        filepath=output_path,
                        frame_start=int(strip.frame_final_start),
                        overlap=0,
                    )
                elif strip.type == "SCENE":
                    # Insert the rendered file as a movie strip and sound strip in the original scene.
                    bpy.ops.sequencer.movie_strip_add(
                        channel=insert_channel,
                        filepath=output_path,
                        frame_start=int(strip.frame_final_start),
                        overlap=0,
                    )
                else:
                    # Insert the rendered file as a movie strip in the original scene without sound.
                    bpy.ops.sequencer.movie_strip_add(
                        channel=insert_channel,
                        filepath=output_path,
                        frame_start=int(strip.frame_final_start),
                        overlap=0,
                        sound=False,
                    )

            # Redraw UI to display the new strip. Remove this if Blender crashes: https://docs.blender.org/api/current/info_gotcha.html#can-i-redraw-during-script-execution
            bpy.ops.wm.redraw_timer(type="DRAW_WIN_SWAP", iterations=1)

            # Reset current frame
            bpy.context.scene.frame_current = current_frame_old
        return {"FINISHED"}


def menu_func(self, context):
    self.layout.separator()
    self.layout.operator(RenderSelectedStripsOperator.bl_idname, icon="SEQ_STRIP_DUPLICATE")


def register():
    bpy.utils.register_class(RenderSelectedStripsOperator)
    bpy.types.SEQUENCER_MT_add.append(menu_func)


def unregister():
    bpy.types.SEQUENCER_MT_strip.remove(menu_func)
    bpy.utils.unregister_class(RenderSelectedStripsOperator)


if __name__ == "__main__":
    register()
