import streamlit as st
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from pydub import AudioSegment
import speech_recognition as sr
import os
import io
import json
from flask import Flask, request, send_file
from pptx import Presentation
from pptx.util import Pt
from pptx.dml.color import RGBColor
import scraping1  # Importing refined transcript generation

# Load the pre-trained tokenizer and model
@st.cache_resource
def load_model():
    tokenizer = AutoTokenizer.from_pretrained("facebook/bart-large-cnn")
    model = AutoModelForSeq2SeqLM.from_pretrained("facebook/bart-large-cnn")
    return tokenizer, model

tokenizer, model = load_model()
AudioSegment.converter = "/path/to/ffmpeg"

def process_audio(file_path):
    try:
        temp_file_path = "temp_uploaded_audio.wav"
        with open(temp_file_path, "wb") as f:
            f.write(file_path.read())
        
        audio = AudioSegment.from_file(temp_file_path)
        mono_audio = audio.set_channels(1)
        converted_audio_path = "temp_audio.wav"
        mono_audio.export(converted_audio_path, format="wav")
        
        recognizer = sr.Recognizer()
        with sr.AudioFile(converted_audio_path) as source:
            audio_data = recognizer.record(source)
            transcribed_text = recognizer.recognize_google(audio_data)
        
        return transcribed_text
    except Exception as e:
        return f"Error processing audio: {e}"

def summarize_text(text):
    input_ids = tokenizer(f"summarize: {text}", return_tensors='pt').input_ids
    outputs = model.generate(input_ids, max_length=130, min_length=30, length_penalty=2.0, num_beams=4)
    return tokenizer.decode(outputs[0], skip_special_tokens=True)

def generate_ppt_and_notes(transcript):
    summary = summarize_text(transcript)
    
    template_path = "presentations/geometric.pptx"
    filepath = "slides.json"
    scraping1.generate_notes(transcript)

    with open(filepath, "r") as file:
        slides_data = json.load(file)
    ppt_file = create_ppt(slides_data, template_path)
    

    return ppt_file

def create_ppt(slide_data, template_path):
    prs = Presentation(template_path)
    
    while len(prs.slides) > 0:
        xml_slides = prs.slides._sldIdLst
        prs.part.drop_rel(xml_slides[0].rId)
        del xml_slides[0]
    
    for slide_content in slide_data:
        title = slide_content["title"]
        points = slide_content["points"]
        
        slide_layout = prs.slide_layouts[2]
        slide = prs.slides.add_slide(slide_layout)
        
        slide_title = slide.shapes.title
        slide_title.text = title
        slide_title.text_frame.paragraphs[0].font.size = Pt(32)
        slide_title.text_frame.paragraphs[0].font.bold = True
        slide_title.text_frame.paragraphs[0].font.color.rgb = RGBColor(255, 69, 0)
        
        content = slide.placeholders[1].text_frame
        
        for point in points:
            p = content.add_paragraph()
            p.text = point
            p.font.size = Pt(14)
            p.font.color.rgb = RGBColor(50, 50, 50)
            p.font.name = "Calibri"
    
    ppt_stream = io.BytesIO()
    prs.save(ppt_stream)
    ppt_stream.seek(0)
    return ppt_stream

st.title("Automated Lecture Processing")
st.write("Upload an audio file to generate lecture notes and presentation.")

uploaded_file = st.file_uploader("Upload Audio File (WAV format)", type=["wav"])

if uploaded_file:
    with st.spinner("Processing audio..."):
        transcribed_text = process_audio(uploaded_file)
        if transcribed_text and not transcribed_text.startswith("Error"):
            ppt_file = generate_ppt_and_notes(transcribed_text)
            st.success("Lecture notes and presentation generated successfully!")
            st.download_button("Download Presentation", ppt_file, file_name="lecture_notes.pptx")
        else:
            st.error(transcribed_text)
