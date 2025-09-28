import axios from 'axios';

// It's a good practice to set the base URL of your API
// You might need to configure CORS on your Flask backend
const apiClient = axios.create({
    baseURL: 'http://127.0.0.1:5000/api',
    headers: {
        'Content-Type': 'application/json',
    },
});

const api = {
    getRoles: async() => {
        const response = await apiClient.get('/roles');
        return response.data.roles;
    },

    getContexts: async(roleAlias) => {
        const response = await apiClient.get(`/roles/${roleAlias}/contexts`);
        return response.data.contexts;
    },

    getContext: async(roleAlias, contextName) => {
        const response = await apiClient.get(`/roles/${roleAlias}/contexts/${contextName}`);
        return response.data;
    },

    deleteContext: async(roleAlias, contextName) => {
        await apiClient.delete(`/roles/${roleAlias}/contexts/${contextName}`);
    },

    renameContext: async(roleAlias, oldContextName, newContextName) => {
        await apiClient.put(`/roles/${roleAlias}/contexts/${oldContextName}`, { new_context_name: newContextName });
    },

    createContext: async(roleAlias, contextName) => {
        const response = await apiClient.post(`/roles/${roleAlias}/contexts`, { context_name: contextName });
        return response.data;
    },

    getRolePrompt: async(roleAlias) => {
        const response = await apiClient.get(`/roles/${roleAlias}/prompt`);
        return response.data;
    },

    updateRolePrompt: async(roleAlias, prompt) => {
        const response = await apiClient.put(`/roles/${roleAlias}/prompt`, { prompt });
        return response.data;
    },

    getRoleImage: async(roleAlias) => {
        const response = await apiClient.get(`/roles/${roleAlias}/image`, {
            responseType: 'blob'
        });
        return URL.createObjectURL(response.data);
    },

    chat: async(roleAlias, inputMsg, contextName, signal = null) => {
        const response = await apiClient.post('/chat', {
            role_alias: roleAlias,
            input_msg: inputMsg,
            context_name: contextName,
        }, {
            signal: signal // 添加AbortSignal支持
        });
        return response.data;
    },

    asr: async(audioBlob) => {
        const response = await apiClient.post('/asr', audioBlob, {
            headers: { 'Content-Type': 'audio/wav' },
        });
        return response.data.text;
    },

    tts: async(ttsParams) => {
        const response = await apiClient.post('/tts', ttsParams, { 
            responseType: 'blob' 
        });
        return response.data;
    },

    getTtsOptions: async() => {
        const response = await apiClient.get('/tts/options');
        return response.data;
    },
};

export default api;