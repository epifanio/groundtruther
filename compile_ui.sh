

pyuic5 qtui/app_settings_ui.ui -o pygui/Ui_app_settings_ui.py
pyuic5 qtui/epsg_ui.ui -o pygui/Ui_epsg_ui.py       
pyuic5 qtui/grass_mdi_ui.ui -o pygui/Ui_grass_mdi_ui.py  
pyuic5 qtui/groundtruther_dockwidget_base.ui -o pygui/Ui_groundtruther_dockwidget_base.py
pyuic5 qtui/image_metadata_ui.ui -o pygui/Ui_image_metadata_ui.py
pyuic5 qtui/paramscale_api_ui.ui -o pygui/Ui_paramscale_ui.py
pyuic5 qtui/query_builder_ui.ui -o pygui/Ui_query_builder_ui.py
pyuic5 qtui/geomorphon_api_ui.ui -o pygui/Ui_geomorphon_ui.py
pyuic5 qtui/grassapi_settings_ui.ui -o pygui/Ui_grass_settings_ui.py
pyuic5 qtui/grm_lsi_ui.ui -o pygui/Ui_grm_lsi_ui.py  
pyuic5 qtui/hbc_browser_ui.ui -o pygui/Ui_hbc_browser_ui.py               
pyuic5 qtui/kmlsave_ui.ui -o pygui/Ui_kmlsave_ui.py

sed -i -e '$s/import resources_rc/import groundtruther.resources_rc/' pygui/Ui_app_settings_ui.py
sed -i -e '$s/import resources_rc/import groundtruther.resources_rc/' pygui/Ui_epsg_ui.py       
sed -i -e '$s/import resources_rc/import groundtruther.resources_rc/' pygui/Ui_grass_mdi_ui.py  
sed -i -e '$s/import resources_rc/import groundtruther.resources_rc/' pygui/Ui_groundtruther_dockwidget_base.py
sed -i -e '$s/import resources_rc/import groundtruther.resources_rc/' pygui/Ui_image_metadata_ui.py
sed -i -e '$s/import resources_rc/import groundtruther.resources_rc/' pygui/Ui_paramscale_ui.py
sed -i -e '$s/import resources_rc/import groundtruther.resources_rc/' pygui/Ui_query_builder_ui.py
sed -i -e '$s/import resources_rc/import groundtruther.resources_rc/' pygui/Ui_geomorphon_ui.py
sed -i -e '$s/import resources_rc/import groundtruther.resources_rc/' pygui/Ui_grass_settings_ui.py
sed -i -e '$s/import resources_rc/import groundtruther.resources_rc/' pygui/Ui_grm_lsi_ui.py  
sed -i -e '$s/import resources_rc/import groundtruther.resources_rc/' pygui/Ui_hbc_browser_ui.py               
sed -i -e '$s/import resources_rc/import groundtruther.resources_rc/' pygui/Ui_kmlsave_ui.py

# pyuic5 <(xmlstarlet ed -d '//ui/resources' qtui/app_settings_ui.ui) -o pygui/Ui_app_settings_ui.py
# pyuic5 <(xmlstarlet ed -d '//ui/resources' qtui/epsg_ui.ui) -o pygui/Ui_epsg_ui.py       
# pyuic5 <(xmlstarlet ed -d '//ui/resources' qtui/grass_mdi_ui.ui) -o pygui/Ui_grass_mdi_ui.py  
# pyuic5 <(xmlstarlet ed -d '//ui/resources' qtui/groundtruther_dockwidget_base.ui) -o pygui/Ui_groundtruther_dockwidget_base.py
# pyuic5 <(xmlstarlet ed -d '//ui/resources' qtui/image_metadata_ui.ui) -o pygui/Ui_image_metadata_ui.py
# pyuic5 <(xmlstarlet ed -d '//ui/resources' qtui/paramscale_api_ui.ui) -o pygui/Ui_paramscale_ui.py
# pyuic5 <(xmlstarlet ed -d '//ui/resources' qtui/query_builder_ui.ui) -o pygui/Ui_query_builder_ui.py
# pyuic5 <(xmlstarlet ed -d '//ui/resources' qtui/geomorphon_api_ui.ui) -o pygui/Ui_geomorphon_ui.py
# pyuic5 <(xmlstarlet ed -d '//ui/resources' qtui/grassapi_settings_ui.ui) -o pygui/Ui_grass_settings_ui.py
# pyuic5 <(xmlstarlet ed -d '//ui/resources' qtui/grm_lsi_ui.ui) -o pygui/Ui_grm_lsi_ui.py  
# pyuic5 <(xmlstarlet ed -d '//ui/resources' qtui/hbc_browser_ui.ui) -o pygui/Ui_hbc_browser_ui.py               
# pyuic5 <(xmlstarlet ed -d '//ui/resources' qtui/kmlsave_ui.ui) -o pygui/Ui_kmlsave_ui.py

# app_settings_gui.py  
# epsg_search_gui.py  
# grass_settings_gui.py  
# image_metadata_gui.py
# epsg.py              
# grass_mdi_gui.py    
# hbc_browser_gui.py     
# kmlsave_gui.py         
# querybuilder_gui.py